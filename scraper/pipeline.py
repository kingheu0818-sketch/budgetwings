from __future__ import annotations

from collections.abc import Iterable

from models.deal import Deal


def deduplicate_deals(deals: Iterable[Deal]) -> list[Deal]:
    seen: set[tuple[str, str, str, int]] = set()
    unique_deals: list[Deal] = []
    for deal in deals:
        key = (deal.origin_city, deal.destination_city, deal.departure_date.isoformat(), deal.price_cny_fen)
        if key in seen:
            continue
        seen.add(key)
        unique_deals.append(deal)
    return unique_deals


def normalize_deals(deals: Iterable[Deal]) -> list[Deal]:
    return sorted(
        deduplicate_deals(deals),
        key=lambda deal: (deal.departure_date, deal.price_cny_fen, deal.destination_city),
    )
