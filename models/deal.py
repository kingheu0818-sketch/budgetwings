from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class TransportMode(StrEnum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"
    CARPOOL = "carpool"


class Deal(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str = Field(min_length=1, description="Data source identifier.")
    origin_city: str = Field(min_length=1)
    origin_code: str | None = Field(default=None, description="Airport, station, or city code.")
    destination_city: str = Field(min_length=1)
    destination_code: str | None = Field(
        default=None,
        description="Airport, station, or city code.",
    )
    destination_country: str | None = None
    price_cny_fen: int = Field(ge=0, description="Price stored in CNY fen.")
    transport_mode: TransportMode
    departure_date: date
    return_date: date | None = None
    is_round_trip: bool = False
    operator: str | None = Field(
        default=None,
        description="Airline, rail operator, or bus company.",
    )
    booking_url: HttpUrl
    source_url: HttpUrl | None = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    notes: str | None = None

    @field_validator("scraped_at", "expires_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "datetime fields must be timezone-aware"
            raise ValueError(msg)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.return_date is not None and self.return_date < self.departure_date:
            msg = "return_date must be on or after departure_date"
            raise ValueError(msg)
        if self.is_round_trip and self.return_date is None:
            msg = "round-trip deals require return_date"
            raise ValueError(msg)
        return self
