from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from config import Settings
from llm.base import ChatMessage, LLMAdapter, ToolCallResult, ToolSchema
from models.deal import Deal, TransportMode
from tools.currency import CurrencyConvertInput, CurrencyTool
from tools.holiday import HolidayInput, HolidayTool
from tools.price_parser import PriceParserInput, PriceParserTool
from tools.visa import VisaLookupInput, VisaTool
from tools.weather import WeatherInput, WeatherTool
from tools.web_fetch import WebFetchInput, WebFetchTool
from tools.web_search import WebSearchInput, WebSearchTool


class FakeLLM(LLMAdapter):
    def __init__(
        self,
        response: str = "ok",
        structured_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(model="fake")
        self.response = response
        self.structured_response = structured_response or {"deals": []}

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        return self.response

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        return {"provider": "fake", "tool_calls": []}

    async def extract_structured(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        return self.structured_response


class FakeSearchTool(WebSearchTool):
    async def _search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        return [{"title": "Deal", "url": "https://example.com", "content": query}]


class FakeFetchTool(WebFetchTool):
    async def _fetch_html(self, url: str) -> str:
        return "<html><body><script>bad()</script><main>Cheap flight CNY 199</main></body></html>"


class FakeWeatherTool(WeatherTool):
    async def _lookup(self, city: str, country: str | None, days: int) -> dict[str, Any]:
        return {"city": city, "country": country, "forecast": {"time": ["2026-05-01"]}}


class FakeCurrencyTool(CurrencyTool):
    async def _fetch_rates_to_cny(self) -> dict[str, Decimal]:
        return {"CNY": Decimal("1"), "USD": Decimal("7.20")}


def sample_deal(price: int = 19900) -> Deal:
    return Deal.model_validate(
        {
            "source": "test",
            "origin_city": "Shenzhen",
            "destination_city": "Bangkok",
            "price_cny_fen": price,
            "transport_mode": TransportMode.FLIGHT,
            "departure_date": date.today().isoformat(),
            "booking_url": "https://example.com/book",
        }
    )


def test_tool_schema_exports_claude_and_openai_formats() -> None:
    tool = FakeSearchTool()

    claude_schema = tool.to_schema("claude")
    openai_schema = tool.to_schema("openai")

    assert claude_schema["name"] == "web_search"
    assert "input_schema" in claude_schema
    assert openai_schema["type"] == "function"
    assert openai_schema["function"]["name"] == "web_search"


def test_web_search_tool_uses_backend() -> None:
    settings = Settings.model_construct(tavily_api_key="fake")
    result = asyncio.run(FakeSearchTool(settings).execute(WebSearchInput(query="深圳 特价机票")))

    assert result.success is True
    assert isinstance(result.data, list)
    assert result.data[0]["url"] == "https://example.com"


def test_web_search_tool_falls_back_without_tavily_key() -> None:
    settings = Settings.model_construct(tavily_api_key=None)
    result = asyncio.run(WebSearchTool(settings).execute(WebSearchInput(query="深圳 特价机票")))

    assert result.success is True
    assert isinstance(result.data, list)
    assert result.data[0]["title"] == "fallback"
    assert "深圳 特价机票" in result.data[0]["content"]


def test_web_fetch_tool_extracts_text() -> None:
    result = asyncio.run(FakeFetchTool().execute(WebFetchInput(url="https://example.com")))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert "Cheap flight" in result.data["text"]
    assert "bad()" not in result.data["text"]


def test_price_parser_tool_extracts_deals_with_fake_llm() -> None:
    structured = {
        "deals": [
            {
                "origin_city": "深圳",
                "destination_city": "曼谷",
                "price_cny": 199,
                "transport_mode": "flight",
                "departure_date": date.today().isoformat(),
                "booking_url": "https://example.com/book",
                "source_url": "https://example.com/source",
                "evidence_text": "深圳飞曼谷 199",
            }
        ]
    }
    tool = PriceParserTool(FakeLLM(structured_response=structured))

    result = asyncio.run(tool.execute(PriceParserInput(text="深圳飞曼谷 199")))

    assert result.success is True
    assert isinstance(result.data, list)
    assert result.data[0]["price_cny_fen"] == 19900


def test_weather_tool_uses_open_meteo_shape() -> None:
    result = asyncio.run(
        FakeWeatherTool().execute(WeatherInput(city="Bangkok", country="Thailand"))
    )

    assert result.success is True
    assert result.data == {
        "city": "Bangkok",
        "country": "Thailand",
        "forecast": {"time": ["2026-05-01"]},
    }


def test_currency_tool_converts_with_rates() -> None:
    result = asyncio.run(
        FakeCurrencyTool().execute(
            CurrencyConvertInput(amount=100, from_currency="USD", to_currency="CNY")
        )
    )

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["amount"] == 720.0


def test_visa_tool_reads_local_json() -> None:
    result = asyncio.run(
        VisaTool().execute(
            VisaLookupInput(destination_city="Bangkok", destination_country="Thailand")
        )
    )

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["visa_type"] == "visa_free"


def test_holiday_tool_returns_bridge_plans() -> None:
    result = asyncio.run(HolidayTool().execute(HolidayInput(year=2026, max_leave_days=2)))

    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["holidays"]
    assert result.data["bridge_plans"][0]["leave_days"] == 2
