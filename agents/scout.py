from __future__ import annotations

import logging
from datetime import date

from agents.base import BaseAgent
from models.deal import Deal
from tools.base import ToolOutput
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

        snippets: list[str] = []
        urls: list[str] = []
        seen_snippets: set[str] = set()
        for category, queries in self._build_query_groups(origin_city).items():
            category_seen: set[str] = set()
            for query in queries:
                logger.info("Scout searching category=%s query=%s", category, query)
                result = await search_tool.execute(WebSearchInput(query=query, max_results=8))
                for item in self._items_from_result(result):
                    key = self._result_key(item)
                    if key in category_seen:
                        continue
                    category_seen.add(key)
                    snippet = self._snippet_from_item(item)
                    if snippet not in seen_snippets:
                        seen_snippets.add(snippet)
                        snippets.append(snippet)
                    url = str(item.get("url", ""))
                    if url.startswith(("http://", "https://")):
                        urls.append(url)

        for url in self._top_urls(urls, limit=3):
            logger.info("Scout fetching URL: %s", url)
            result = await fetch_tool.execute(WebFetchInput(url=url, max_chars=3000))
            if not result.success:
                logger.warning("Scout skipped failed URL: %s error=%s", url, result.error)
                continue
            if isinstance(result.data, dict):
                text = str(result.data.get("text", ""))
                if text:
                    snippets.append(f"Fetched page\n{url}\n{text}")

        source_note = (
            f"价格参考自 {date.today().isoformat()} Tavily 搜索结果，"
            "实际价格请以订票平台为准"
        )
        parse_result = await parser_tool.execute(
            PriceParserInput(
                text="\n\n".join([*snippets, f"Source note: {source_note}"]),
                origin_city=origin_city,
                max_price_cny=max_price,
            )
        )
        if not parse_result.success:
            logger.warning("Scout price parsing failed: %s", parse_result.error)
            return []
        raw_deals = parse_result.data if isinstance(parse_result.data, list) else []
        deals: list[Deal] = []
        for item in raw_deals:
            if not isinstance(item, dict):
                continue
            deal = Deal.model_validate(item)
            notes = deal.notes or source_note
            if "Tavily" not in notes:
                notes = f"{notes}；{source_note}"
            deals.append(deal.model_copy(update={"notes": notes}))
        return deals

    def _build_query_groups(self, origin_city: str) -> dict[str, list[str]]:
        return {
            "international_budget_airlines": [
                f"{origin_city} 飞 曼谷 特价",
                f"{origin_city} 飞 清迈 机票",
                f"{origin_city} 飞 东京 廉航",
                f"cheap flights from {origin_city} May 2026",
            ],
            "airline_promotions": [
                f"{origin_city} 春秋航空 特价",
                f"{origin_city} 亚洲航空 促销",
            ],
            "train_discounts": [
                f"{origin_city} 高铁 特价票 学生票 折扣",
            ],
            "weekend_trips": [
                f"{origin_city} 周末 短途旅行 低价推荐",
            ],
        }

    def _snippets_from_result(self, result: ToolOutput) -> list[str]:
        return [self._snippet_from_item(item) for item in self._items_from_result(result)]

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

    def _urls_from_result(self, result: ToolOutput) -> list[str]:
        if not result.success or not isinstance(result.data, list):
            return []
        snippets: list[str] = []
        for item in result.data:
            if isinstance(item, dict):
                url = str(item.get("url", ""))
                if url.startswith(("http://", "https://")):
                    snippets.append(url)
        return snippets

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
