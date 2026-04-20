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

        queries = self._build_queries(origin_city)
        snippets: list[str] = []
        urls: list[str] = []
        for query in queries:
            logger.info("Scout searching query: %s", query)
            result = await search_tool.execute(WebSearchInput(query=query, max_results=8))
            snippets.extend(self._snippets_from_result(result))
            urls.extend(self._urls_from_result(result))

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

    def _build_queries(self, origin_city: str) -> list[str]:
        return [
            f"{origin_city} 出发 特价机票 2026年5月",
            f"cheap flights from {origin_city} May 2026",
            f"{origin_city} 出发 特价火车票 高铁折扣",
            f"{origin_city} 五一 低价出行 旅游推荐",
        ]

    def _snippets_from_result(self, result: ToolOutput) -> list[str]:
        if not result.success or not isinstance(result.data, list):
            return []
        snippets: list[str] = []
        for item in result.data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", ""))
            url = str(item.get("url", ""))
            content = str(item.get("content", ""))
            snippets.append(f"Search result\n{title}\n{url}\n{content}")
        return snippets

    def _urls_from_result(self, result: ToolOutput) -> list[str]:
        if not result.success or not isinstance(result.data, list):
            return []
        urls: list[str] = []
        for item in result.data:
            if isinstance(item, dict):
                url = str(item.get("url", ""))
                if url.startswith(("http://", "https://")):
                    urls.append(url)
        return urls

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
