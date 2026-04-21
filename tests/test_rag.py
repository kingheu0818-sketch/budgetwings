from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import rag.seed_data as seed_data
from agents.guide import GuideAgent
from llm.base import ChatMessage, LLMAdapter, ToolCallResult, ToolSchema
from models.deal import Deal, TransportMode
from models.persona import PersonaType
from rag.knowledge_base import KnowledgeBase
from tools.base import BaseTool, ToolInput, ToolOutput


class FakeLLM(LLMAdapter):
    def __init__(self) -> None:
        super().__init__(model="fake")
        self.last_messages: list[ChatMessage] = []

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        self.last_messages = messages
        return "# Guide"

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        return {"tool_calls": []}

    async def extract_structured(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        return {"deals": []}


class FakeSearchTool(BaseTool):
    name = "web_search"
    description = "fake search"

    async def execute(self, input: ToolInput) -> ToolOutput:
        return ToolOutput(success=True, data=[{"title": "tip", "content": "latest tip"}])


class FakeKnowledge:
    def search(self, query: str, top_k: int = 5) -> list[str]:
        return [f"{query} visa-free reference", "Use local transit card."]


def test_knowledge_base_add_and_search(tmp_path: Path) -> None:
    knowledge_base = KnowledgeBase(
        db_path=tmp_path,
        embedding_fn=_test_embedding,
        prefer_lancedb=False,
    )
    knowledge_base.add_destination_info(
        city="Chiang Mai",
        country="Thailand",
        info_text="Chiang Mai uses Thai Baht and is good for weekend temples.",
    )
    knowledge_base.add_deal_history(_deal())

    results = knowledge_base.search("Chiang Mai Thai Baht", top_k=2)

    assert results
    assert any("Chiang Mai" in result for result in results)


def test_seed_data_runs_with_temp_store(tmp_path: Path, monkeypatch: Any) -> None:
    visa_path = tmp_path / "visa_policies.json"
    visa_path.write_text(
        json.dumps(
            [
                {
                    "city": "Bangkok",
                    "country": "Thailand",
                    "visa_type": "visa_free",
                    "summary": "Verify current policy.",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(seed_data, "VISA_POLICY_PATH", visa_path)

    count = seed_data.seed_knowledge_base(db_path=tmp_path / "knowledge")

    assert count == 1
    assert (tmp_path / "knowledge" / "knowledge.json").exists()


def test_guide_agent_uses_knowledge_base_context() -> None:
    llm = FakeLLM()
    guide = GuideAgent(llm, [FakeSearchTool()], knowledge_base=FakeKnowledge())

    markdown = asyncio.run(guide.generate(_deal(), PersonaType.WORKER))

    assert markdown == "# Guide"
    prompt = str(llm.last_messages[-1]["content"])
    assert "以下是关于Chiang Mai的参考信息" in prompt
    assert "visa-free reference" in prompt


def test_guide_agent_without_knowledge_base_still_works() -> None:
    llm = FakeLLM()
    guide = GuideAgent(llm, [FakeSearchTool()])

    markdown = asyncio.run(guide.generate(_deal(), PersonaType.STUDENT))

    assert markdown == "# Guide"
    prompt = str(llm.last_messages[-1]["content"])
    assert "以下是关于Chiang Mai的参考信息" not in prompt


def _deal() -> Deal:
    return Deal.model_validate(
        {
            "source": "test",
            "origin_city": "Shenzhen",
            "destination_city": "Chiang Mai",
            "destination_country": "Thailand",
            "price_cny_fen": 68000,
            "transport_mode": TransportMode.FLIGHT,
            "departure_date": "2026-05-20",
            "booking_url": "https://example.com/book",
        }
    )


def _test_embedding(text: str) -> list[float]:
    lower = text.casefold()
    return [
        1.0 if "chiang" in lower else 0.0,
        1.0 if "thai" in lower else 0.0,
        1.0 if "deal" in lower else 0.0,
    ]
