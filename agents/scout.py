from __future__ import annotations

import logging
from datetime import date

from agents.base import BaseAgent
from models.deal import Deal
from tools.base import BaseTool, ToolOutput
from tools.destinations import DESTINATION_ALIASES
from tools.price_parser import PriceParserInput
from tools.web_fetch import WebFetchInput
from tools.web_search import WebSearchInput

logger = logging.getLogger(__name__)


class ScoutAgent(BaseAgent):
    name = "scout"

    async def discover(self, origin_city: str, days: int = 60, max_price: int = 1500) -> list[Deal]:
        search_tool = self.require_tool("web_search")
        fetch_tool = self.require_tool("web_fetch")
        parser_tool = self.require_tool("price_parser")
        source_note = (
            f"价格参考自 {date.today().isoformat()} Tavily 搜索结果，"
            "实际价格请以订票平台为准"
        )

        destinations = await self._discover_destinations(search_tool, origin_city)
        logger.info("Scout destination candidates for %s: %s", origin_city, destinations)

        deals: list[Deal] = []
        for destination in destinations:
            context = await self._context_for_destination(
                search_tool=search_tool,
                fetch_tool=fetch_tool,
                origin_city=origin_city,
                destination=destination,
            )
            if not context:
                logger.info(
                    "Scout skipped destination=%s because no context was found",
                    destination,
                )
                continue

            parse_result = await parser_tool.execute(
                PriceParserInput(
                    text="\n\n".join(
                        [
                            f"Target destination: {destination}",
                            *context,
                            f"Source note: {source_note}",
                        ]
                    ),
                    origin_city=origin_city,
                    max_price_cny=max_price,
                )
            )
            if not parse_result.success:
                logger.warning(
                    "Scout price parsing failed for destination=%s: %s",
                    destination,
                    parse_result.error,
                )
                continue
            raw_deals = parse_result.data if isinstance(parse_result.data, list) else []
            destination_deals = self._validated_deals(raw_deals, destination, source_note)
            deals.extend(destination_deals[:2])
        return deals

    async def _discover_destinations(self, search_tool: BaseTool, origin_city: str) -> list[str]:
        scores = dict.fromkeys(DESTINATION_ALIASES, 0)
        for query in self._discovery_queries(origin_city):
            logger.info("Scout discovering destinations query=%s", query)
            result = await search_tool.execute(WebSearchInput(query=query, max_results=8))
            for item in self._items_from_result(result):
                text = self._snippet_from_item(item)
                for destination, aliases in DESTINATION_ALIASES.items():
                    if any(alias.casefold() in text.casefold() for alias in aliases):
                        scores[destination] += 1

        discovered = [
            destination
            for destination, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
            if score > 0
        ]
        if discovered:
            return discovered[:6]
        return ["曼谷", "清迈", "东京", "大阪", "首尔", "三亚"]

    async def _context_for_destination(
        self,
        search_tool: BaseTool,
        fetch_tool: BaseTool,
        origin_city: str,
        destination: str,
    ) -> list[str]:
        snippets: list[str] = []
        urls: list[str] = []
        seen: set[str] = set()
        for query in self._destination_queries(origin_city, destination):
            logger.info("Scout searching destination=%s query=%s", destination, query)
            result = await search_tool.execute(WebSearchInput(query=query, max_results=8))
            for item in self._items_from_result(result):
                key = self._result_key(item)
                if key in seen:
                    continue
                seen.add(key)
                snippets.append(self._snippet_from_item(item))
                url = str(item.get("url", ""))
                if url.startswith(("http://", "https://")):
                    urls.append(url)

        for url in self._top_urls(urls, limit=2):
            logger.info("Scout fetching destination=%s URL=%s", destination, url)
            result = await fetch_tool.execute(WebFetchInput(url=url, max_chars=3000))
            if not result.success:
                logger.warning(
                    "Scout skipped failed destination=%s URL=%s error=%s",
                    destination,
                    url,
                    result.error,
                )
                continue
            if isinstance(result.data, dict):
                text = str(result.data.get("text", ""))
                if text:
                    snippets.append(f"Fetched page\n{url}\n{text}")
        return snippets

    def _validated_deals(
        self,
        raw_deals: list[object],
        destination: str,
        source_note: str,
    ) -> list[Deal]:
        deals: list[Deal] = []
        for item in raw_deals:
            if not isinstance(item, dict):
                continue
            deal = Deal.model_validate(item)
            if not self._matches_destination(deal.destination_city, destination):
                logger.info(
                    "Scout skipped parsed deal destination=%s for target=%s",
                    deal.destination_city,
                    destination,
                )
                continue
            notes = deal.notes or source_note
            if "Tavily" not in notes:
                notes = f"{notes}；{source_note}"
            deals.append(deal.model_copy(update={"notes": notes}))
        return sorted(deals, key=lambda deal: (deal.price_cny_fen, deal.departure_date))

    def _discovery_queries(self, origin_city: str) -> list[str]:
        return [
            f"{origin_city} 五一 低价出行 旅游推荐",
            f"{origin_city} 周末 短途旅行 低价推荐",
            f"{origin_city} 出发 特价机票 2026年5月",
            f"{origin_city} 春秋航空 亚洲航空 特价 目的地",
        ]

    def _destination_queries(self, origin_city: str, destination: str) -> list[str]:
        aliases = list(DESTINATION_ALIASES.get(destination, {destination}))
        english_alias = next(
            (alias for alias in aliases if alias.isascii() and len(alias) > 3),
            destination,
        )
        return [
            f"{origin_city} 飞 {destination} 特价",
            f"{origin_city} 飞 {destination} 机票",
            f"{origin_city} {destination} 廉航 促销",
            f"{origin_city} 春秋航空 {destination} 特价",
            f"{origin_city} 亚洲航空 {destination} 促销",
            f"cheap flights from {origin_city} to {english_alias} May 2026",
        ]

    def _items_from_result(self, result: ToolOutput) -> list[dict[str, object]]:
        if not result.success or not isinstance(result.data, list):
            return []
        return [item for item in result.data if isinstance(item, dict)]

    def _snippet_from_item(self, item: dict[str, object]) -> str:
        title = str(item.get("title", ""))
        url = str(item.get("url", ""))
        content = str(item.get("content", ""))
        return f"Search result\n{title}\n{url}\n{content}"

    def _result_key(self, item: dict[str, object]) -> str:
        url = str(item.get("url", "")).strip().casefold()
        if url:
            return url
        title = str(item.get("title", "")).strip().casefold()
        content = str(item.get("content", "")).strip().casefold()
        return f"{title}|{content[:160]}"

    def _top_urls(self, urls: list[str], limit: int) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            unique.append(url)
            if len(unique) >= limit:
                break
        return unique

    def _matches_destination(self, parsed_destination: str, target_destination: str) -> bool:
        parsed = parsed_destination.casefold()
        aliases = DESTINATION_ALIASES.get(target_destination, {target_destination})
        return any(alias.casefold() in parsed or parsed in alias.casefold() for alias in aliases)
