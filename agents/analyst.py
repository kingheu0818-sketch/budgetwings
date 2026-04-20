from __future__ import annotations

from collections.abc import Iterable

from agents.base import BaseAgent
from engine.deal_ranker import rank_deals
from engine.persona_filter import filter_deals
from models.deal import Deal
from models.persona import PersonaType, default_persona_filter


class AnalystAgent(BaseAgent):
    name = "analyst"

    async def analyze(
        self,
        deals: Iterable[Deal],
        persona_type: PersonaType,
        top_n: int = 10,
    ) -> list[Deal]:
        unique_deals = self._deduplicate(deals)
        persona = default_persona_filter(persona_type)
        filtered = filter_deals(unique_deals, persona)
        ranked = rank_deals(filtered, persona)
        return ranked[:top_n]

    def _deduplicate(self, deals: Iterable[Deal]) -> list[Deal]:
        seen: set[tuple[str, str, str, int]] = set()
        unique: list[Deal] = []
        for deal in deals:
            key = (
                deal.origin_city,
                deal.destination_city,
                deal.departure_date.isoformat(),
                deal.price_cny_fen,
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(deal)
        return unique
