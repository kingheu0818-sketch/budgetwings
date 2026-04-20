from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from db.analytics import get_cheapest_ever, get_price_trend, is_historical_low
from db.engine import create_db_and_tables
from db.models import SearchLog
from db.repository import get_latest_deals, get_price_history, save_deals, save_search_log
from models.deal import Deal, TransportMode


def test_save_deals_and_price_history() -> None:
    engine = memory_engine()
    deal = make_deal(price=68000)

    save_deals([deal], engine=engine)

    latest = get_latest_deals(limit=10, engine=engine)
    history = get_price_history("深圳", "清迈", days=30, engine=engine)
    assert len(latest) == 1
    assert latest[0].id == deal.id
    assert latest[0].is_valid is True
    assert len(history) == 1
    assert history[0].price_cny_fen == 68000


def test_save_invalid_deal_record() -> None:
    engine = memory_engine()
    deal = make_deal(price=0)

    save_deals(
        [deal],
        engine=engine,
        is_valid=False,
        validation_errors={deal.id: ["price must be positive"]},
    )

    latest = get_latest_deals(limit=10, engine=engine)
    history = get_price_history("深圳", "清迈", days=30, engine=engine)
    assert latest == []
    assert history == []


def test_save_search_log() -> None:
    engine = memory_engine()
    log = SearchLog(city="深圳", persona="worker", status="success", deal_count=3)

    save_search_log(log, engine=engine)

    # Saving the same id again should update rather than duplicate.
    log.deal_count = 5
    save_search_log(log, engine=engine)
    latest = get_latest_deals(limit=10, engine=engine)
    assert latest == []


def test_price_analytics() -> None:
    engine = memory_engine()
    expensive = make_deal(price=100000)
    cheap = make_deal(price=68000)
    pricey_now = make_deal(price=120000)

    assert is_historical_low(expensive, engine=engine) is True
    save_deals([expensive], engine=engine)
    assert is_historical_low(cheap, engine=engine) is True
    save_deals([cheap], engine=engine)
    assert is_historical_low(pricey_now, engine=engine) is False
    assert get_cheapest_ever("深圳", "清迈", engine=engine) == 68000

    trend = get_price_trend("深圳", "清迈", days=30, engine=engine)
    assert [item["price_cny_fen"] for item in trend] == [100000, 68000]


def memory_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_db_and_tables(engine)
    return engine


def make_deal(price: int) -> Deal:
    return Deal.model_validate(
        {
            "source": "test",
            "origin_city": "深圳",
            "destination_city": "清迈",
            "destination_country": "Thailand",
            "price_cny_fen": price,
            "transport_mode": TransportMode.FLIGHT,
            "departure_date": (date.today() + timedelta(days=14)).isoformat(),
            "booking_url": "https://example.com/book",
        }
    )
