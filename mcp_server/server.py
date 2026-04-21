from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

from agents.analyst import AnalystAgent
from agents.guide import GuideAgent
from agents.orchestrator import build_llm
from agents.scout import ScoutAgent
from bot.data import load_latest_deals, ranked_deals
from config import Settings, get_settings
from db.analytics import get_price_trend
from db.repository import get_latest_deals
from models.deal import Deal
from models.persona import PersonaType
from rag.knowledge_base import KnowledgeBase
from tools.price_parser import PriceParserTool
from tools.visa import VisaTool
from tools.weather import WeatherInput, WeatherTool
from tools.web_fetch import WebFetchTool
from tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)

mcp_server_module: Any | None

try:
    import mcp.server as mcp_server_module
except Exception:  # pragma: no cover - exercised only without optional SDK.
    mcp_server_module = None


class MCPServices:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.knowledge_base = self._build_knowledge_base()
        self.search_tool = WebSearchTool(settings)
        self.fetch_tool = WebFetchTool(settings)
        self.weather_tool = WeatherTool()
        self.visa_tool = VisaTool()
        self.scout: ScoutAgent | None = None
        self.analyst: AnalystAgent | None = None
        self.guide: GuideAgent | None = None

    async def search_deals(self, city: str, persona: str, top_n: int = 10) -> list[dict[str, Any]]:
        persona_type = PersonaType(persona)
        scout, analyst, _ = self._ensure_agent_stack()
        raw_deals = await scout.discover(city)
        ranked = await analyst.analyze(raw_deals, persona_type, top_n=top_n)
        return [deal.model_dump(mode="json") for deal in ranked]

    async def get_guide(
        self,
        deal_id: str | None = None,
        destination: str | None = None,
        persona: str = PersonaType.WORKER.value,
    ) -> str:
        persona_type = PersonaType(persona)
        deal = self._resolve_deal(
            deal_id=deal_id,
            destination=destination,
            persona_type=persona_type,
        )
        stored_guide = self._load_guide_markdown(deal.id)
        if stored_guide is not None:
            return stored_guide
        _, _, guide = self._ensure_agent_stack()
        return await guide.generate(deal, persona_type)

    async def price_trend(
        self,
        origin: str,
        destination: str,
        days: int = 30,
    ) -> list[dict[str, object]]:
        return get_price_trend(origin, destination, days=days)

    async def visa_check(self, destination: str) -> dict[str, Any]:
        city, country = self._resolve_destination(destination)
        return self.visa_tool.lookup(country, city)

    async def weather_check(self, city: str) -> dict[str, Any]:
        result = await self.weather_tool.execute(WeatherInput(city=city))
        if not result.success or not isinstance(result.data, dict):
            msg = result.error or f"Failed to fetch weather for {city}"
            raise RuntimeError(msg)
        return cast(dict[str, Any], result.data)

    def _resolve_deal(
        self,
        deal_id: str | None,
        destination: str | None,
        persona_type: PersonaType,
    ) -> Deal:
        if deal_id:
            deal = self._find_deal_by_id(deal_id)
            if deal is not None:
                return deal
            msg = f"Deal not found: {deal_id}"
            raise ValueError(msg)
        if not destination:
            msg = "Either deal_id or destination is required"
            raise ValueError(msg)
        normalized = destination.casefold()
        latest_deals = ranked_deals(persona_type)
        for deal in latest_deals:
            if normalized in deal.destination_city.casefold():
                return deal
        msg = f"No latest deal found for destination: {destination}"
        raise ValueError(msg)

    def _find_deal_by_id(self, deal_id: str) -> Deal | None:
        for record in get_latest_deals(limit=200):
            if record.id == deal_id:
                return Deal.model_validate(
                    {
                        "id": record.id,
                        "source": record.source,
                        "origin_city": record.origin_city,
                        "origin_code": record.origin_code,
                        "destination_city": record.destination_city,
                        "destination_code": record.destination_code,
                        "destination_country": record.destination_country,
                        "price_cny_fen": record.price_cny_fen,
                        "transport_mode": record.transport_mode,
                        "departure_date": record.departure_date,
                        "return_date": record.return_date,
                        "is_round_trip": record.is_round_trip,
                        "operator": record.operator,
                        "booking_url": record.booking_url,
                        "source_url": record.source_url,
                        "scraped_at": record.scraped_at,
                        "expires_at": record.expires_at,
                        "notes": record.notes,
                    }
                )
        for deal in load_latest_deals():
            if deal.id == deal_id:
                return deal
        return None

    def _resolve_destination(self, destination: str) -> tuple[str | None, str]:
        payload = json.loads(Path("data/visa_policies.json").read_text(encoding="utf-8"))
        normalized = destination.casefold()
        for item in payload:
            if not isinstance(item, dict):
                continue
            city = str(item.get("city", ""))
            country = str(item.get("country", ""))
            if normalized == city.casefold() or normalized == country.casefold():
                return city or None, country
        return None, destination

    def _build_knowledge_base(self) -> KnowledgeBase | None:
        try:
            return KnowledgeBase()
        except Exception:
            logger.exception("Knowledge base unavailable for MCP server")
            return None

    def _ensure_agent_stack(self) -> tuple[ScoutAgent, AnalystAgent, GuideAgent]:
        if self.scout and self.analyst and self.guide:
            return self.scout, self.analyst, self.guide

        llm = build_llm(self.settings)
        price_parser = PriceParserTool(llm)
        scout = ScoutAgent(llm, [self.search_tool, self.fetch_tool, price_parser])
        analyst = AnalystAgent(llm, [])
        guide = GuideAgent(llm, [self.search_tool], knowledge_base=self.knowledge_base)

        self.scout = scout
        self.analyst = analyst
        self.guide = guide
        return scout, analyst, guide

    def _load_guide_markdown(self, deal_id: str) -> str | None:
        path = Path("data/guides") / f"{deal_id}.md"
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("Failed to read stored guide for deal id=%s", deal_id)
            return None


def create_server(settings: Settings | None = None) -> Any:
    server_class = getattr(mcp_server_module, "FastMCP", None)
    if server_class is None:
        msg = "mcp library is not installed. Install 'mcp>=1.0.0' to use the MCP server."
        raise RuntimeError(msg)

    resolved = settings or get_settings()
    services = MCPServices(resolved)
    server = server_class(
        name="BudgetWings MCP",
        instructions=(
            "BudgetWings MCP tools expose cheap travel search, guide generation, "
            "visa checks, weather checks, and historical price trends."
        ),
        dependencies=["httpx", "sqlmodel"],
        log_level="INFO",
    )

    @server.tool(
        description=(
            "Search and rank cheap travel deals for a city and persona. "
            "按城市和画像搜索并排序低价出行 deal。"
        )
    )
    async def search_deals(
        city: str,
        persona: str = PersonaType.WORKER.value,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        return await services.search_deals(city=city, persona=persona, top_n=top_n)

    @server.tool(
        description=(
            "Generate a travel guide by deal_id or destination and persona. "
            "根据 deal_id 或目的地和画像生成攻略 Markdown。"
        )
    )
    async def get_guide(
        deal_id: str | None = None,
        destination: str | None = None,
        persona: str = PersonaType.WORKER.value,
    ) -> str:
        return await services.get_guide(deal_id=deal_id, destination=destination, persona=persona)

    @server.tool(
        description=(
            "Query historical price trend from the BudgetWings database. "
            "从 BudgetWings 数据库查询历史价格趋势。"
        )
    )
    async def price_trend(origin: str, destination: str, days: int = 30) -> list[dict[str, object]]:
        return await services.price_trend(origin=origin, destination=destination, days=days)

    @server.tool(
        description=(
            "Check visa policy for a destination using local data. "
            "使用本地签证库查询目的地签证政策。"
        )
    )
    async def visa_check(destination: str) -> dict[str, Any]:
        return await services.visa_check(destination=destination)

    @server.tool(
        description=(
            "Check latest weather for a city using the weather tool. "
            "使用天气工具查询城市天气。"
        )
    )
    async def weather_check(city: str) -> dict[str, Any]:
        return await services.weather_check(city=city)

    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    logger.info("Starting BudgetWings MCP server in stdio mode")
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
