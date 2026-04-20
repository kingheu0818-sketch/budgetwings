from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from bot.data import (
    deals_within_budget,
    format_deal_message,
    latest_deals_file,
    load_latest_deals,
    search_deals,
)
from models.deal import Deal, TransportMode
from models.persona import PersonaType


def sample_deals() -> list[Deal]:
    departure = date.today() + timedelta(days=7)
    return [
        Deal.model_validate(
            {
                "source": "test",
                "origin_city": "Shenzhen",
                "destination_city": "Chiang Mai",
                "destination_country": "Thailand",
                "price_cny_fen": 19900,
                "transport_mode": TransportMode.FLIGHT,
                "departure_date": departure.isoformat(),
                "booking_url": "https://example.com/cnx",
            }
        ),
        Deal.model_validate(
            {
                "source": "test",
                "origin_city": "Shenzhen",
                "destination_city": "Bangkok",
                "destination_country": "Thailand",
                "price_cny_fen": 52000,
                "transport_mode": TransportMode.FLIGHT,
                "departure_date": departure.isoformat(),
                "booking_url": "https://example.com/bkk",
            }
        ),
    ]


def test_load_sample_deals(tmp_path: Path) -> None:
    deals_dir = tmp_path / "deals"
    deals_dir.mkdir()
    payload = [deal.model_dump(mode="json") for deal in sample_deals()]
    (deals_dir / "2026-04-20.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    path = latest_deals_file(deals_dir)

    assert path is not None
    assert path.name == "2026-04-20.json"
    assert len(load_latest_deals(deals_dir)) == 2


def test_search_deals_by_destination() -> None:
    deals = search_deals("Chiang", PersonaType.WORKER, sample_deals())

    assert len(deals) == 1
    assert deals[0].destination_city == "Chiang Mai"


def test_budget_filter_and_message_format() -> None:
    deals = deals_within_budget(200, PersonaType.STUDENT, sample_deals())

    assert deals
    message = format_deal_message(deals[0])
    assert "💰 ¥" in message
    assert "🔗 订票链接：" in message
