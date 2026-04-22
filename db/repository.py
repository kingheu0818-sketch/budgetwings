from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from db.engine import create_db_and_tables, get_database_engine
from db.models import DealRecord, PriceHistory, SearchLog
from models.deal import Deal


def build_deals_snapshot_path(
    output_dir: Path,
    *,
    mode: str = "run",
    now: datetime | None = None,
) -> Path:
    timestamp = now or datetime.now()
    safe_mode = _snapshot_mode(mode)
    filename = (
        f"{timestamp.date().isoformat()}_{safe_mode}_{timestamp.strftime('%H%M%S')}.json"
    )
    return output_dir / filename


def save_deals(
    deals: list[Deal],
    engine: Engine | None = None,
    *,
    is_valid: bool = True,
    validation_errors: Mapping[str, list[str]] | None = None,
) -> None:
    resolved_engine = _ensure_engine(engine)
    with Session(resolved_engine) as session:
        for deal in deals:
            record = deal_to_record(
                deal,
                is_valid=is_valid,
                validation_errors=validation_errors.get(deal.id) if validation_errors else None,
            )
            session.merge(record)
            if is_valid:
                session.add(
                    PriceHistory(
                        origin_city=deal.origin_city,
                        destination_city=deal.destination_city,
                        transport_mode=deal.transport_mode.value,
                        price_cny_fen=deal.price_cny_fen,
                    )
                )
        session.commit()


def save_search_log(log: SearchLog, engine: Engine | None = None) -> None:
    resolved_engine = _ensure_engine(engine)
    with Session(resolved_engine) as session:
        session.merge(log)
        session.commit()


def get_price_history(
    origin: str,
    destination: str,
    days: int = 30,
    engine: Engine | None = None,
) -> list[PriceHistory]:
    resolved_engine = _ensure_engine(engine)
    since = datetime.now(UTC) - timedelta(days=days)
    with Session(resolved_engine) as session:
        statement = (
            select(PriceHistory)
            .where(PriceHistory.origin_city == origin)
            .where(PriceHistory.destination_city == destination)
            .where(PriceHistory.observed_at >= since)
        )
        return sorted(session.exec(statement).all(), key=lambda item: item.observed_at)


def get_latest_deals(limit: int = 20, engine: Engine | None = None) -> list[DealRecord]:
    resolved_engine = _ensure_engine(engine)
    with Session(resolved_engine) as session:
        statement = (
            select(DealRecord)
            .where(DealRecord.is_valid == True)  # noqa: E712
        )
        records = sorted(
            session.exec(statement).all(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        return list(records[:limit])


def deal_to_record(
    deal: Deal,
    *,
    is_valid: bool = True,
    validation_errors: list[str] | None = None,
) -> DealRecord:
    return DealRecord(
        id=deal.id,
        source=deal.source,
        origin_city=deal.origin_city,
        origin_code=deal.origin_code,
        destination_city=deal.destination_city,
        destination_code=deal.destination_code,
        destination_country=deal.destination_country,
        price_cny_fen=deal.price_cny_fen,
        transport_mode=deal.transport_mode.value,
        departure_date=deal.departure_date,
        return_date=deal.return_date,
        is_round_trip=deal.is_round_trip,
        operator=deal.operator,
        booking_url=str(deal.booking_url),
        source_url=str(deal.source_url) if deal.source_url else None,
        scraped_at=deal.scraped_at,
        expires_at=deal.expires_at,
        notes=deal.notes,
        is_valid=is_valid,
        validation_errors=json.dumps(validation_errors, ensure_ascii=False)
        if validation_errors
        else None,
    )


def _ensure_engine(engine: Engine | None) -> Engine:
    resolved_engine = engine or get_database_engine()
    create_db_and_tables(resolved_engine)
    return resolved_engine


def _snapshot_mode(mode: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "_" for char in mode)
    collapsed = normalized.strip("_")
    return collapsed or "run"
