from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, cast

from llm.base import ChatMessage, LLMAdapter, LLMError, ToolCallResult, ToolSchema
from llm.openai_adapter import OpenAIAdapter
from models.deal import Deal
from tools.price_parser import PriceParserInput, PriceParserTool


class StructuredLLM(LLMAdapter):
    def __init__(self, structured_response: Any) -> None:
        super().__init__(model="structured-fake")
        self.structured_response = structured_response

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        del messages, tools
        return "unused"

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        del messages, tools
        return {"provider": "fake", "tool_calls": []}

    async def extract_structured(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        if isinstance(self.structured_response, Exception):
            raise self.structured_response
        return cast(dict[str, Any], self.structured_response)


def test_price_parser_execute_returns_valid_deals() -> None:
    payload = {
        "deals": [
            {
                "origin_city": "深圳",
                "destination_city": "曼谷",
                "price_cny": 299,
                "transport_mode": "flight",
                "departure_date": (date.today() + timedelta(days=20)).isoformat(),
                "booking_url": "https://example.com/book",
                "source_url": "https://example.com/source",
                "evidence_text": "深圳飞曼谷 299 元",
            }
        ]
    }
    tool = PriceParserTool(StructuredLLM(payload))

    result = asyncio.run(
        tool.execute(PriceParserInput(text="深圳飞曼谷 299 元", origin_city="深圳"))
    )

    assert result.success is True
    assert isinstance(result.data, list)
    assert len(result.data) == 1
    Deal.model_validate(result.data[0])


def test_price_parser_execute_handles_llm_error() -> None:
    tool = PriceParserTool(StructuredLLM(LLMError("boom")))

    result = asyncio.run(tool.execute(PriceParserInput(text="irrelevant", origin_city="深圳")))

    assert result.success is False
    assert result.error == "boom"


def test_price_parser_execute_handles_invalid_structured_payload_gracefully() -> None:
    tool = PriceParserTool(StructuredLLM("this is not json"))

    result = asyncio.run(tool.execute(PriceParserInput(text="garbage", origin_city="深圳")))

    assert result.success is False
    assert result.error is not None


def test_price_parser_execute_allows_empty_structured_result() -> None:
    tool = PriceParserTool(StructuredLLM({"deals": []}))

    result = asyncio.run(tool.execute(PriceParserInput(text="没有明确价格", origin_city="深圳")))

    assert result.success is True
    assert result.data == []


def test_openai_extract_structured_falls_back_to_tool_use() -> None:
    adapter = cast(Any, object.__new__(OpenAIAdapter))
    adapter.model = "fake-model"
    adapter.timeout_seconds = 1.0
    adapter.tracer = None

    calls: list[str] = []

    async def fail_response_format(
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        calls.append("response_format")
        raise RuntimeError("response_format unsupported")

    async def succeed_tool_use(
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        calls.append("tool_use")
        return {"deals": []}

    adapter._extract_via_response_format = fail_response_format
    adapter._extract_via_tool_use = succeed_tool_use

    result = asyncio.run(
        adapter.extract_structured(
            messages=[{"role": "user", "content": "extract deals"}],
            schema={"type": "object"},
            schema_name="deal_list",
            schema_description="Extract deals",
        )
    )

    assert result == {"deals": []}
    assert calls == ["response_format", "tool_use"]
