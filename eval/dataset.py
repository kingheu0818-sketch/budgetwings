from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from models.deal import TransportMode

GOLDEN_DEALS_PATH = Path("eval/golden_deals.json")


class GoldenDeal(BaseModel):
    model_config = ConfigDict(frozen=True)

    origin_city: str = Field(min_length=1)
    destination_city: str = Field(min_length=1)
    price_range_min: int = Field(ge=0, description="Reasonable lower price bound in CNY yuan.")
    price_range_max: int = Field(ge=0, description="Reasonable upper price bound in CNY yuan.")
    transport_mode: TransportMode
    is_international: bool


def load_golden_deals(path: Path = GOLDEN_DEALS_PATH) -> list[GoldenDeal]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        msg = f"Golden deals file must contain a list: {path}"
        raise ValueError(msg)
    return [GoldenDeal.model_validate(item) for item in payload]


def filter_golden_deals(
    deals: list[GoldenDeal],
    origin_cities: list[str] | None = None,
) -> list[GoldenDeal]:
    if not origin_cities:
        return deals
    normalized = {city.casefold() for city in origin_cities}
    return [deal for deal in deals if deal.origin_city.casefold() in normalized]
