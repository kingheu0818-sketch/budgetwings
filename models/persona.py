from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.deal import TransportMode


class PersonaType(StrEnum):
    WORKER = "worker"
    STUDENT = "student"


class PersonaFilterParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    persona_type: PersonaType
    max_one_way_price_cny_fen: int = Field(ge=0)
    min_departure_days_ahead: int = Field(ge=0)
    max_departure_days_ahead: int = Field(ge=0)
    include_red_eye: bool
    max_layover_minutes: int | None = Field(default=None, ge=0)
    preferred_transport_modes: list[TransportMode]
    default_sort: Literal["date", "price"]


class WorkerFilterParams(PersonaFilterParams):
    persona_type: PersonaType = PersonaType.WORKER
    max_one_way_price_cny_fen: int = 150_000
    min_departure_days_ahead: int = 0
    max_departure_days_ahead: int = 35
    include_red_eye: bool = False
    max_layover_minutes: int | None = 180
    preferred_transport_modes: list[TransportMode] = Field(
        default_factory=lambda: [TransportMode.FLIGHT, TransportMode.TRAIN, TransportMode.BUS]
    )
    default_sort: Literal["date", "price"] = "date"


class StudentFilterParams(PersonaFilterParams):
    persona_type: PersonaType = PersonaType.STUDENT
    max_one_way_price_cny_fen: int = 50_000
    min_departure_days_ahead: int = 30
    max_departure_days_ahead: int = 90
    include_red_eye: bool = True
    max_layover_minutes: int | None = None
    preferred_transport_modes: list[TransportMode] = Field(
        default_factory=lambda: [TransportMode.TRAIN, TransportMode.FLIGHT, TransportMode.BUS]
    )
    default_sort: Literal["date", "price"] = "price"


def default_persona_filter(persona_type: PersonaType) -> PersonaFilterParams:
    if persona_type is PersonaType.WORKER:
        return WorkerFilterParams()
    return StudentFilterParams()
