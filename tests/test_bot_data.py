from __future__ import annotations

from pathlib import Path

from bot.data import (
    deals_within_budget,
    format_deal_message,
    latest_deals_file,
    load_latest_deals,
    search_deals,
)
from models.persona import PersonaType


def test_load_sample_deals() -> None:
    path = latest_deals_file(Path("data/deals"))

    assert path is not None
    assert path.name == "2026-04-20.json"
    assert len(load_latest_deals(Path("data/deals"))) == 15


def test_search_deals_by_destination() -> None:
    deals = search_deals("清迈", PersonaType.WORKER)

    assert len(deals) == 1
    assert deals[0].destination_city == "清迈"


def test_budget_filter_and_message_format() -> None:
    deals = deals_within_budget(200, PersonaType.STUDENT)

    assert deals
    message = format_deal_message(deals[0])
    assert "💰 ¥" in message
    assert "🔗 订票链接：" in message
