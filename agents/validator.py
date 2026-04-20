from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date
from typing import NamedTuple
from urllib.parse import urlparse

from models.deal import Deal, TransportMode

logger = logging.getLogger(__name__)

CHINA_ALIASES = {"china", "cn", "中国", "中國", "prc", "mainland china"}


class ValidationResult(NamedTuple):
    valid_deals: list[Deal]
    errors: list[str]


def validate_deals(deals: Iterable[Deal], today: date | None = None) -> ValidationResult:
    reference_date = today or date.today()
    valid_deals: list[Deal] = []
    errors: list[str] = []
    for deal in deals:
        deal_errors = validate_deal(deal, reference_date)
        if deal_errors:
            reason = "; ".join(deal_errors)
            errors.append(f"{deal.id}: {reason}")
            logger.warning(
                "Discarded invalid deal id=%s route=%s->%s reason=%s",
                deal.id,
                deal.origin_city,
                deal.destination_city,
                reason,
            )
            continue
        valid_deals.append(deal)
    return ValidationResult(valid_deals=valid_deals, errors=errors)


def validate_deal(deal: Deal, today: date | None = None) -> list[str]:
    reference_date = today or date.today()
    errors: list[str] = []

    if deal.price_cny_fen <= 0:
        errors.append("price must be positive")
    else:
        min_price, max_price = _price_range_for(deal)
        if deal.price_cny_fen < min_price or deal.price_cny_fen > max_price:
            errors.append(
                f"price {deal.price_cny_fen} outside range {min_price}-{max_price}",
            )

    if deal.departure_date <= reference_date:
        errors.append("departure_date must be after today")

    if not _is_valid_https_url(str(deal.booking_url)):
        errors.append("booking_url must be a valid https URL")

    if deal.origin_city.strip().casefold() == deal.destination_city.strip().casefold():
        errors.append("origin_city and destination_city must differ")

    if deal.is_round_trip and deal.return_date is None:
        errors.append("round trip deals require return_date")

    return errors


def _price_range_for(deal: Deal) -> tuple[int, int]:
    if deal.transport_mode is TransportMode.TRAIN:
        return 100, 300_000
    if deal.transport_mode is TransportMode.BUS:
        return 100, 200_000
    if deal.transport_mode is TransportMode.FLIGHT and _is_international(deal):
        return 100, 2_000_000
    if deal.transport_mode is TransportMode.FLIGHT:
        return 100, 500_000
    return 100, 500_000


def _is_international(deal: Deal) -> bool:
    country = (deal.destination_country or "").strip().casefold()
    return bool(country and country not in CHINA_ALIASES)


def _is_valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)
