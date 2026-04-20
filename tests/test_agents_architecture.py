from __future__ import annotations

import asyncio
from datetime import date, timedelta

from agents.analyst import AnalystAgent
from agents.guide import GuideAgent
from agents.scout import ScoutAgent
from llm.base import ChatMessage, LLMAdapter, ToolCallResult, ToolSchema
from models.deal import Deal, TransportMode
from models.persona import PersonaType
from tools.base import BaseTool, ToolInput, ToolOutput


class FakeLLM(LLMAdapter):
    def __init__(self, response: str = "# Guide") -> None:
        super().__init__(model="fake")
        self.response = response

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
        return {"tool_calls": []}


class FakeSearchTool(BaseTool):
    name = "web_search"
    description = "fake search"

    async def execute(self, input: ToolInput) -> ToolOutput:
        return ToolOutput(
            success=True,
            data=[
                {
                    "title": "Cheap flight",
                    "url": "https://example.com",
                    "content": "Shenzhen to Bangkok CNY 199",
                }
            ],
        )


class FakeParserTool(BaseTool):
    name = "price_parser"
    description = "fake parser"

    async def execute(self, input: ToolInput) -> ToolOutput:
        return ToolOutput(success=True, data=[deal().model_dump(mode="json")])


def deal(price: int = 19900, days_ahead: int = 7) -> Deal:
    return Deal.model_validate(
        {
            "source": "test",
            "origin_city": "Shenzhen",
            "destination_city": "Bangkok",
            "price_cny_fen": price,
            "transport_mode": TransportMode.FLIGHT,
            "departure_date": (date.today() + timedelta(days=days_ahead)).isoformat(),
            "booking_url": "https://example.com/book",
        }
    )


def test_scout_agent_discovers_deals() -> None:
    scout = ScoutAgent(FakeLLM(), [FakeSearchTool(), FakeParserTool()])

    deals = asyncio.run(scout.discover("Shenzhen"))

    assert len(deals) == 1
    assert deals[0].destination_city == "Bangkok"


def test_analyst_agent_deduplicates_and_ranks() -> None:
    analyst = AnalystAgent(FakeLLM(), [])
    raw_deals = [deal(price=30000), deal(price=19900), deal(price=19900)]

    ranked = asyncio.run(analyst.analyze(raw_deals, PersonaType.STUDENT, top_n=10))

    assert len(ranked) == 2
    assert ranked[0].price_cny_fen == 19900


def test_guide_agent_generates_markdown() -> None:
    guide = GuideAgent(FakeLLM("# Bangkok guide"), [FakeSearchTool()])

    markdown = asyncio.run(guide.generate(deal(), PersonaType.WORKER))

    assert markdown == "# Bangkok guide"
