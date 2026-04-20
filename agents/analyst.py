from __future__ import annotations

import logging
from collections import defaultdict, deque
from collections.abc import Iterable

from agents.base import BaseAgent
from db.analytics import is_historical_low
from engine.deal_ranker import rank_deals
from engine.persona_filter import filter_deals
from models.deal import Deal
from models.persona import PersonaType, default_persona_filter

logger = logging.getLogger(__name__)


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
        limited = self._limit_origin_destination(filtered, max_per_pair=2)
        ranked = rank_deals(limited, persona)
        diversified = self._diversify_destinations(ranked)
        annotated = self._annotate_historical_lows(diversified)
        return annotated[:top_n]

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

    def _limit_origin_destination(
        self,
        deals: Iterable[Deal],
        max_per_pair: int,
    ) -> list[Deal]:
        grouped: dict[tuple[str, str], list[Deal]] = defaultdict(list)
        for deal in deals:
            grouped[(deal.origin_city, deal.destination_city)].append(deal)

        limited: list[Deal] = []
        for group in grouped.values():
            cheapest = sorted(group, key=lambda deal: (deal.price_cny_fen, deal.departure_date))
            limited.extend(cheapest[:max_per_pair])
        return limited

    def _diversify_destinations(self, deals: list[Deal]) -> list[Deal]:
        grouped: dict[str, deque[Deal]] = defaultdict(deque)
        destination_order: list[str] = []
        for deal in deals:
            if deal.destination_city not in grouped:
                destination_order.append(deal.destination_city)
            grouped[deal.destination_city].append(deal)

        diversified: list[Deal] = []
        while any(grouped.values()):
            for destination in destination_order:
                if grouped[destination]:
                    diversified.append(grouped[destination].popleft())
        return diversified

    def _annotate_historical_lows(self, deals: list[Deal]) -> list[Deal]:
        annotated: list[Deal] = []
        for deal in deals:
            try:
                historical_low = is_historical_low(deal)
            except Exception:
                logger.exception("Failed to check historical low for deal id=%s", deal.id)
                annotated.append(deal)
                continue
            if not historical_low:
                annotated.append(deal)
                continue
            notes = deal.notes or ""
            if "历史低价" not in notes:
                notes = f"{notes}\n🔥 历史低价".strip()
            annotated.append(deal.model_copy(update={"notes": notes}))
        return annotated
