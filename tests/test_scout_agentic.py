from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from agents.scout import ScoutAgent
from llm.base import ChatMessage, LLMAdapter, ToolCallResult, ToolSchema
from models.deal import Deal
from tools.base import BaseTool, ToolInput, ToolOutput


class ScriptedLLM(LLMAdapter):
    def __init__(self, responses: list[ToolCallResult]) -> None:
        super().__init__(model="scripted-scout")
        self.responses = responses
        self.index = 0

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        del messages, tools
        return ""

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        del messages, tools
        if self.index >= len(self.responses):
            return {"provider": "fake", "stop_reason": "end_turn", "content": []}
        response = self.responses[self.index]
        self.index += 1
        return response

    async def extract_structured(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        return {"deals": []}


class AgenticSearchTool(BaseTool):
    name = "web_search"
    description = "fake search"

    async def execute(self, input: ToolInput) -> ToolOutput:
        query = getattr(input, "query", "")
        if "低价旅行" in query:
            return ToolOutput(
                success=True,
                data=[
                    {
                        "title": "曼谷特价",
                        "url": "https://example.com/search/bangkok",
                        "content": "深圳飞曼谷 2026-05-12 单程 399 元，春秋航空",
                    }
                ],
            )
        if "西安" in query:
            return ToolOutput(
                success=True,
                data=[
                    {
                        "title": "西安特价",
                        "url": "https://example.com/search/xian",
                        "content": "深圳飞西安 2026-05-28 单程 430 元，南方航空",
                    }
                ],
            )
        return ToolOutput(
            success=True,
            data=[
                {
                    "title": "杂项结果",
                    "url": "https://example.com/search/other",
                    "content": "没有明确价格",
                }
            ],
        )


class AgenticFetchTool(BaseTool):
    name = "web_fetch"
    description = "fake fetch"

    async def execute(self, input: ToolInput) -> ToolOutput:
        url = getattr(input, "url", "")
        if "bangkok" in url:
            return ToolOutput(
                success=True,
                data={
                    "url": url,
                    "text": (
                        "页面详情：深圳飞曼谷 2026-05-12 单程 399 元，春秋航空，"
                        "预订链接 https://example.com/book/bangkok"
                    ),
                },
            )
        return ToolOutput(success=True, data={"url": url, "text": "空白页面"})


class DummyPriceParserTool(BaseTool):
    name = "price_parser"
    description = "unused parser"

    async def execute(self, input: ToolInput) -> ToolOutput:
        del input
        return ToolOutput(success=True, data=[])


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_call", "id": call_id, "name": name, "arguments": arguments}


def test_agentic_scout_happy_path_submits_and_finishes() -> None:
    departure = (date.today() + timedelta(days=30)).isoformat()
    llm = ScriptedLLM(
        [
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("1", "web_search", {"query": "深圳 周末 低价旅行"})],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("2", "web_fetch", {"url": "https://example.com/search/bangkok"})],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [
                    tool_call(
                        "3",
                        "submit_deal",
                        {
                            "origin_city": "深圳",
                            "destination_city": "曼谷",
                            "price_cny": 399,
                            "transport_mode": "flight",
                            "departure_date": departure,
                            "operator": "春秋航空",
                            "booking_url": "https://example.com/book/bangkok",
                            "source_url": "https://example.com/search/bangkok",
                            "evidence_text": "深圳飞曼谷 2026-05-12 单程 399 元，春秋航空",
                        },
                    )
                ],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("4", "finish", {"reason": "enough deals"})],
            },
        ]
    )
    scout = ScoutAgent(
        llm,
        [AgenticSearchTool(), AgenticFetchTool(), DummyPriceParserTool()],
        mode="agentic",
    )

    deals = asyncio.run(scout.discover("深圳"))

    assert len(deals) == 1
    assert deals[0].destination_city == "曼谷"
    assert scout.last_run_stats["stop_reason"] == "enough deals"
    assert scout.last_run_stats["accepted_deal_count"] == 1


def test_agentic_scout_stops_when_tool_budget_exhausted() -> None:
    llm = ScriptedLLM(
        [
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("1", "web_search", {"query": "深圳 周末 低价旅行"})],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("2", "web_search", {"query": "深圳 周末 低价旅行"})],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("3", "web_search", {"query": "深圳 周末 低价旅行"})],
            },
        ]
    )
    scout = ScoutAgent(
        llm,
        [AgenticSearchTool(), AgenticFetchTool(), DummyPriceParserTool()],
        mode="agentic",
        max_tool_calls=2,
    )

    deals = asyncio.run(scout.discover("深圳"))

    assert deals == []
    assert scout.last_run_stats["stop_reason"] == "tool_budget_exhausted"
    assert scout.last_run_stats["tool_call_count"] == 2


def test_agentic_scout_rejects_invalid_evidence() -> None:
    departure = (date.today() + timedelta(days=30)).isoformat()
    llm = ScriptedLLM(
        [
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("1", "web_search", {"query": "深圳 周末 低价旅行"})],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [
                    tool_call(
                        "2",
                        "submit_deal",
                        {
                            "origin_city": "深圳",
                            "destination_city": "曼谷",
                            "price_cny": 399,
                            "transport_mode": "flight",
                            "departure_date": departure,
                            "booking_url": "https://example.com/book/bangkok",
                            "evidence_text": "完全不在上下文里的伪造句子 399 元飞曼谷",
                        },
                    )
                ],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("3", "finish", {"reason": "done"})],
            },
        ]
    )
    scout = ScoutAgent(
        llm,
        [AgenticSearchTool(), AgenticFetchTool(), DummyPriceParserTool()],
        mode="agentic",
    )

    deals = asyncio.run(scout.discover("深圳"))

    assert deals == []
    assert scout.last_run_stats["rejection_by_reason"]["evidence_not_in_source"] == 1


def test_agentic_scout_handles_unknown_tool_without_crashing() -> None:
    llm = ScriptedLLM(
        [
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("1", "haha_unknown", {"foo": "bar"})],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("2", "finish", {"reason": "recovered"})],
            },
        ]
    )
    scout = ScoutAgent(
        llm,
        [AgenticSearchTool(), AgenticFetchTool(), DummyPriceParserTool()],
        mode="agentic",
    )

    deals = asyncio.run(scout.discover("深圳"))

    assert deals == []
    assert scout.last_run_stats["stop_reason"] == "recovered"


def test_agentic_scout_stops_on_plain_text_without_tool_call() -> None:
    llm = ScriptedLLM(
        [
            {
                "provider": "fake",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "I think there are no good deals."}],
            }
        ]
    )
    scout = ScoutAgent(
        llm,
        [AgenticSearchTool(), AgenticFetchTool(), DummyPriceParserTool()],
        mode="agentic",
    )

    deals = asyncio.run(scout.discover("深圳"))

    assert deals == []
    assert scout.last_run_stats["stop_reason"] == "no_tool_call"
    assert scout.last_run_stats["tool_call_count"] == 0


def test_agentic_scout_outputs_deal_objects() -> None:
    departure = (date.today() + timedelta(days=21)).isoformat()
    llm = ScriptedLLM(
        [
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("1", "web_search", {"query": "深圳 飞 西安 特价"})],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [
                    tool_call(
                        "2",
                        "submit_deal",
                        {
                            "origin_city": "深圳",
                            "destination_city": "西安",
                            "price_cny": 430,
                            "transport_mode": "flight",
                            "departure_date": departure,
                            "booking_url": "https://example.com/book/xian",
                            "evidence_text": "深圳飞西安 2026-05-28 单程 430 元",
                        },
                    )
                ],
            },
            {
                "provider": "fake",
                "stop_reason": "tool_use",
                "content": [tool_call("3", "finish", {"reason": "done"})],
            },
        ]
    )
    scout = ScoutAgent(
        llm,
        [AgenticSearchTool(), AgenticFetchTool(), DummyPriceParserTool()],
        mode="agentic",
    )

    deals = asyncio.run(scout.discover("深圳"))

    assert len(deals) == 1
    assert isinstance(deals[0], Deal)
