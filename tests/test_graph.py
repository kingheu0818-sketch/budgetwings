from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from agents.graph import GraphPipeline
from agents.validator import validate_deal, validate_deals
from models.deal import Deal, TransportMode
from models.persona import PersonaType


class FakeScout:
    def __init__(self, batches: list[list[Deal]]) -> None:
        self.batches = batches
        self.calls = 0
        self.days_seen: list[int] = []
        self.max_prices_seen: list[int] = []

    async def discover(self, origin_city: str, days: int = 60, max_price: int = 1500) -> list[Deal]:
        self.calls += 1
        self.days_seen.append(days)
        self.max_prices_seen.append(max_price)
        if self.batches:
            return self.batches.pop(0)
        return []


class FakeAnalyst:
    async def analyze(
        self,
        deals: Sequence[Deal],
        persona_type: PersonaType,
        top_n: int = 10,
    ) -> list[Deal]:
        del persona_type
        return sorted(deals, key=lambda deal: deal.price_cny_fen)[:top_n]


class FakeGuide:
    async def generate(
        self,
        deal: Deal,
        persona_type: PersonaType,
        days: int = 2,
        knowledge_context: str | None = None,
    ) -> str:
        del days
        return (
            f"# {deal.destination_city}\n\n"
            f"Persona: {persona_type.value}\n"
            f"{knowledge_context or ''}"
        )


def make_deal(
    *,
    price: int = 68_000,
    transport_mode: TransportMode = TransportMode.FLIGHT,
    origin_city: str = "深圳",
    destination_city: str = "清迈",
    destination_country: str | None = "Thailand",
    departure_days: int = 14,
    base_date: date | None = None,
    booking_url: str = "https://example.com/book",
    is_round_trip: bool = False,
    return_date: date | None = None,
) -> Deal:
    departure_base = base_date or date.today()
    return Deal.model_validate(
        {
            "source": "test",
            "origin_city": origin_city,
            "destination_city": destination_city,
            "destination_country": destination_country,
            "price_cny_fen": price,
            "transport_mode": transport_mode,
            "departure_date": (departure_base + timedelta(days=departure_days)).isoformat(),
            "return_date": return_date.isoformat() if return_date else None,
            "is_round_trip": is_round_trip,
            "booking_url": booking_url,
        }
    )


def test_graph_declares_expected_nodes(tmp_path: Path) -> None:
    pipeline = GraphPipeline(FakeScout([[make_deal()]]), FakeAnalyst(), FakeGuide(), tmp_path)

    assert pipeline.graph_nodes() == {
        "scout_node",
        "validate_node",
        "analyst_node",
        "retrieve_node",
        "guide_node",
        "save_node",
        "retry_node",
    }


def test_validator_rejects_invalid_deals() -> None:
    today = date(2026, 4, 20)
    invalid_deals = [
        make_deal(price=0),
        make_deal(price=400_000, transport_mode=TransportMode.TRAIN),
        make_deal(departure_days=-1, base_date=today),
        make_deal(booking_url="http://example.com/book"),
        make_deal(origin_city="深圳", destination_city="深圳"),
    ]

    result = validate_deals(invalid_deals, today=today)

    assert result.valid_deals == []
    assert len(result.errors) == len(invalid_deals)
    assert any("price must be positive" in error for error in result.errors)
    assert any("outside range" in error for error in result.errors)
    assert any("departure_date must be after today" in error for error in result.errors)
    assert any("valid https URL" in error for error in result.errors)
    assert any("must differ" in error for error in result.errors)


def test_validator_accepts_valid_deal() -> None:
    result = validate_deal(make_deal(), today=date.today())

    assert result == []


def test_graph_retries_empty_scout_result(tmp_path: Path) -> None:
    valid_deal = make_deal()
    scout = FakeScout([[], [valid_deal]])
    pipeline = GraphPipeline(scout, FakeAnalyst(), FakeGuide(), tmp_path)

    deals = asyncio.run(
        pipeline.run(city="深圳", persona_type=PersonaType.WORKER, top_n=3, output_root=tmp_path)
    )

    assert deals == [valid_deal]
    assert scout.calls == 2
    assert scout.days_seen == [60, 90]
    assert scout.max_prices_seen == [1500, 2000]
    assert list((tmp_path / "deals").glob("*.json"))
    assert list((tmp_path / "guides").glob("*.md"))


def test_graph_saves_empty_result_after_single_retry(tmp_path: Path) -> None:
    scout = FakeScout([[], []])
    pipeline = GraphPipeline(scout, FakeAnalyst(), FakeGuide(), tmp_path)

    deals = asyncio.run(
        pipeline.run(city="深圳", persona_type=PersonaType.WORKER, top_n=3, output_root=tmp_path)
    )

    assert deals == []
    assert scout.calls == 2
    deal_files = list((tmp_path / "deals").glob("*.json"))
    assert deal_files
    assert deal_files[0].read_text(encoding="utf-8").strip() == "[]"
