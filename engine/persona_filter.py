from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from models.deal import Deal
from models.persona import PersonaFilterParams


def filter_deals(
    deals: Iterable[Deal],
    persona: PersonaFilterParams,
    today: date | None = None,
) -> list[Deal]:
    base_date = today or date.today()
    earliest_date = base_date + timedelta(days=persona.min_departure_days_ahead)
    latest_date = base_date + timedelta(days=persona.max_departure_days_ahead)

    return [
        deal
        for deal in deals
        if deal.price_cny_fen <= persona.max_one_way_price_cny_fen
        and earliest_date <= deal.departure_date <= latest_date
        and deal.transport_mode in persona.preferred_transport_modes
    ]
