from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from db.engine import create_db_and_tables, get_database_engine
from db.models import PriceHistory
from db.repository import get_price_history
from models.deal import Deal


def get_price_trend(
    origin: str,
    destination: str,
    days: int = 30,
    engine: Engine | None = None,
) -> list[dict[str, object]]:
    return [
        {
            "origin_city": item.origin_city,
            "destination_city": item.destination_city,
            "transport_mode": item.transport_mode,
            "price_cny_fen": item.price_cny_fen,
            "observed_at": item.observed_at.isoformat(),
        }
        for item in get_price_history(origin, destination, days=days, engine=engine)
    ]


def get_cheapest_ever(
    origin: str,
    destination: str,
    engine: Engine | None = None,
) -> int | None:
    resolved_engine = _ensure_engine(engine)
    with Session(resolved_engine) as session:
        statement = (
            select(PriceHistory)
            .where(PriceHistory.origin_city == origin)
            .where(PriceHistory.destination_city == destination)
        )
        record = min(
            session.exec(statement).all(),
            key=lambda item: item.price_cny_fen,
            default=None,
        )
        return record.price_cny_fen if record else None


def is_historical_low(deal: Deal, engine: Engine | None = None) -> bool:
    cheapest = get_cheapest_ever(deal.origin_city, deal.destination_city, engine=engine)
    return cheapest is None or deal.price_cny_fen <= cheapest


def _ensure_engine(engine: Engine | None) -> Engine:
    resolved_engine = engine or get_database_engine()
    create_db_and_tables(resolved_engine)
    return resolved_engine
