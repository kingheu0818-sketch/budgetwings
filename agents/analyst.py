from __future__ import annotations

from collections import defaultdict, deque
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
        limited = self._limit_origin_destination(filtered, max_per_pair=2)
        ranked = rank_deals(limited, persona)
        diversified = self._diversify_destinations(ranked)
        return diversified[:top_n]

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
