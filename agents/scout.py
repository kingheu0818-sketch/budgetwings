from __future__ import annotations

from agents.base import BaseAgent
from models.deal import Deal
from tools.base import ToolOutput
from tools.price_parser import PriceParserInput
from tools.web_search import WebSearchInput


class ScoutAgent(BaseAgent):
    name = "scout"

    async def discover(self, origin_city: str, days: int = 60, max_price: int = 1500) -> list[Deal]:
        search_tool = self.require_tool("web_search")
        parser_tool = self.require_tool("price_parser")
        queries = [
            f"{origin_city} 出发 特价机票 未来 {days} 天",
            f"{origin_city} 飞 东南亚 廉航 促销",
            f"{origin_city} 低价 火车 大巴 出行 优惠",
        ]

        snippets: list[str] = []
        for query in queries:
            result = await search_tool.execute(WebSearchInput(query=query, max_results=5))
            snippets.extend(self._snippets_from_result(result))

        parse_result = await parser_tool.execute(
            PriceParserInput(
                text="\n\n".join(snippets),
                origin_city=origin_city,
                max_price_cny=max_price,
            )
        )
        if not parse_result.success:
            return []
        raw_deals = parse_result.data if isinstance(parse_result.data, list) else []
        return [Deal.model_validate(item) for item in raw_deals if isinstance(item, dict)]

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
            snippets.append(f"{title}\n{url}\n{content}")
        return snippets
