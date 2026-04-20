from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class DealRecord(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    source: str
    origin_city: str = Field(index=True)
    origin_code: str | None = None
    destination_city: str = Field(index=True)
    destination_code: str | None = None
    destination_country: str | None = None
    price_cny_fen: int = Field(index=True)
    transport_mode: str = Field(index=True)
    departure_date: date = Field(index=True)
    return_date: date | None = None
    is_round_trip: bool = False
    operator: str | None = None
    booking_url: str
    source_url: str | None = None
    scraped_at: datetime
    expires_at: datetime | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    is_valid: bool = Field(default=True, index=True)
    validation_errors: str | None = None


class SearchLog(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    city: str = Field(index=True)
    persona: str = Field(index=True)
    started_at: datetime = Field(default_factory=utc_now, index=True)
    finished_at: datetime | None = None
    status: str = Field(default="started", index=True)
    deal_count: int = 0
    error_messages: str | None = None
    token_usage: str | None = None


class PriceHistory(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    origin_city: str = Field(index=True)
    destination_city: str = Field(index=True)
    transport_mode: str = Field(index=True)
    price_cny_fen: int = Field(index=True)
    observed_at: datetime = Field(default_factory=utc_now, index=True)
