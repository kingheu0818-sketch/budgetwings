from __future__ import annotations

from models.deal import Deal


def format_deal_notification(deal: Deal) -> str:
    price_yuan = deal.price_cny_fen / 100
    return f"{deal.origin_city} -> {deal.destination_city} CNY {price_yuan:.0f} on {deal.departure_date}"
