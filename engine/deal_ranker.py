from __future__ import annotations

from collections.abc import Sequence

from models.deal import Deal
from models.persona import PersonaFilterParams


def rank_deals(deals: Sequence[Deal], persona: PersonaFilterParams) -> list[Deal]:
    if persona.default_sort == "price":
        return sorted(deals, key=lambda deal: (deal.price_cny_fen, deal.departure_date))
    return sorted(deals, key=lambda deal: (deal.departure_date, deal.price_cny_fen))
