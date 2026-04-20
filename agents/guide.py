from __future__ import annotations

import logging
from typing import Protocol

from agents.base import BaseAgent
from llm.base import LLMAdapter, LLMError
from models.deal import Deal
from models.persona import PersonaType
from tools.base import BaseTool
from tools.web_search import WebSearchInput

logger = logging.getLogger(__name__)

PERSONA_INSTRUCTIONS: dict[PersonaType, str] = {
    PersonaType.WORKER: (
        "Target user is a busy worker: keep the trip efficient, recommend hotels "
        "around CNY 200-500/night, food around CNY 50-150/person, and allow taxis "
        "when they save time."
    ),
    PersonaType.STUDENT: (
        "Target user is a student: optimize for ultra-low budget, hostels around "
        "CNY 30-100/night, street food under CNY 30/person, free attractions, and "
        "public transit or walking."
    ),
}


class KnowledgeSearchLike(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[str]:
        ...


class GuideAgent(BaseAgent):
    name = "guide"

    def __init__(
        self,
        llm: LLMAdapter,
        tools: list[BaseTool],
        knowledge_base: KnowledgeSearchLike | None = None,
    ) -> None:
        super().__init__(llm, tools)
        self.knowledge_base = knowledge_base

    async def generate(
        self,
        deal: Deal,
        persona_type: PersonaType,
        days: int = 2,
        knowledge_context: str | None = None,
    ) -> str:
        resolved_knowledge = knowledge_context
        if resolved_knowledge is None:
            resolved_knowledge = self._knowledge_context(deal.destination_city)
        search_context = await self._destination_context(deal.destination_city)
        prompt = self._build_prompt(
            deal,
            persona_type,
            days,
            search_context,
            resolved_knowledge,
        )
        try:
            return await self.llm.chat(
                [
                    {"role": "system", "content": "You are a practical travel guide writer."},
                    {"role": "user", "content": prompt},
                ]
            )
        except LLMError:
            return self._fallback_guide(deal, persona_type, days)

    async def _destination_context(self, destination_city: str) -> str:
        tool = self.tools.get("web_search")
        if tool is None:
            return ""
        result = await tool.execute(
            WebSearchInput(query=f"{destination_city} travel guide latest tips", max_results=5)
        )
        if not result.success or not isinstance(result.data, list):
            return ""
        return "\n".join(str(item) for item in result.data)

    def _knowledge_context(self, destination_city: str) -> str:
        if self.knowledge_base is None:
            return ""
        try:
            chunks = self.knowledge_base.search(destination_city, top_k=5)
        except Exception:
            logger.exception("Knowledge base search failed for destination=%s", destination_city)
            return ""
        return "\n\n".join(chunks)

    def _build_prompt(
        self,
        deal: Deal,
        persona_type: PersonaType,
        days: int,
        context: str,
        knowledge_context: str,
    ) -> str:
        price_yuan = deal.price_cny_fen // 100
        rag_section = ""
        if knowledge_context:
            rag_section = (
                f"以下是关于{deal.destination_city}的参考信息，请基于这些信息生成攻略，"
                "不要编造与参考信息矛盾的内容：\n"
                f"{knowledge_context}\n\n"
            )
        return (
            f"Generate a {days}-day Markdown travel guide.\n"
            f"Origin: {deal.origin_city}\n"
            f"Destination: {deal.destination_city}\n"
            f"Transport: {deal.transport_mode.value}\n"
            f"Departure date: {deal.departure_date}\n"
            f"Return date: {deal.return_date or 'flexible'}\n"
            f"Ticket price: CNY {price_yuan}\n"
            f"Persona: {persona_type.value}\n"
            f"{PERSONA_INSTRUCTIONS[persona_type]}\n\n"
            "Include visa notes, weather/clothing, morning/afternoon/evening plans, "
            "accommodation, food, local transport, budget, warnings, and saving tips.\n\n"
            f"{rag_section}"
            f"Latest web context:\n{context}"
        )

    def _fallback_guide(self, deal: Deal, persona_type: PersonaType, days: int) -> str:
        price_yuan = deal.price_cny_fen // 100
        return (
            f"# {deal.destination_city} {days}-day plan\n\n"
            f"- Route: {deal.origin_city} -> {deal.destination_city}\n"
            f"- Ticket price: CNY {price_yuan}\n"
            f"- Persona: {persona_type.value}\n\n"
            "LLM guide generation failed. Verify visa, weather, lodging, and booking "
            "details before departure."
        )
