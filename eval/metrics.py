from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from eval.dataset import GoldenDeal
from models.deal import Deal

CITY_NORMALIZATION = {
    "娣卞湷": "深圳",
    "鍖椾含": "北京",
    "涓婃捣": "上海",
    "骞垮窞": "广州",
    "鎴愰兘": "成都",
    "閲嶅簡": "重庆",
    "婀涙睙": "湛江",
    "棣栧皵": "首尔",
    "鏇艰胺": "曼谷",
    "娓呰繄": "清迈",
    "涓滀含": "东京",
    "澶ч槳": "大阪",
    "涓変簹": "三亚",
    "娴峰彛": "海口",
}


@dataclass(frozen=True)
class EvaluationMetrics:
    price_accuracy: float
    destination_recall: float
    destination_precision: float
    url_validity: float
    data_freshness: float
    diversity_score: float
    matched_price_count: int
    output_count: int
    golden_count: int

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def calculate_metrics(
    golden_deals: list[GoldenDeal],
    output_deals: list[Deal],
) -> EvaluationMetrics:
    relevant_golden = _relevant_golden(golden_deals, output_deals)
    matched = _matched_pairs(relevant_golden, output_deals)
    valid_urls = sum(1 for deal in output_deals if _is_valid_https_url(str(deal.booking_url)))
    today = datetime.now(UTC).date()
    future_departures = sum(1 for deal in output_deals if deal.departure_date > today)
    unique_destinations = {
        _normalize_city(deal.destination_city).casefold() for deal in output_deals
    }
    golden_destinations = {
        _normalize_city(deal.destination_city).casefold() for deal in relevant_golden
    }
    output_destinations = unique_destinations
    overlapping_destinations = golden_destinations & output_destinations

    return EvaluationMetrics(
        price_accuracy=_safe_ratio(
            sum(1 for golden, deal in matched if _price_in_reasonable_range(golden, deal)),
            len(matched),
        ),
        destination_recall=_safe_ratio(len(overlapping_destinations), len(golden_destinations)),
        destination_precision=_safe_ratio(len(overlapping_destinations), len(output_destinations)),
        url_validity=_safe_ratio(valid_urls, len(output_deals)),
        data_freshness=_safe_ratio(future_departures, len(output_deals)),
        diversity_score=_safe_ratio(len(unique_destinations), len(output_deals)),
        matched_price_count=len(matched),
        output_count=len(output_deals),
        golden_count=len(relevant_golden),
    )


def _relevant_golden(golden_deals: list[GoldenDeal], output_deals: list[Deal]) -> list[GoldenDeal]:
    if not output_deals:
        return golden_deals
    origins = {deal.origin_city.casefold() for deal in output_deals}
    filtered = [deal for deal in golden_deals if deal.origin_city.casefold() in origins]
    return filtered if filtered else golden_deals


def _matched_pairs(
    golden_deals: list[GoldenDeal],
    output_deals: list[Deal],
) -> list[tuple[GoldenDeal, Deal]]:
    golden_index = {
        (
            _normalize_city(golden.origin_city).casefold(),
            _normalize_city(golden.destination_city).casefold(),
            golden.transport_mode.value,
        ): golden
        for golden in golden_deals
    }
    matched: list[tuple[GoldenDeal, Deal]] = []
    for deal in output_deals:
        key = (
            _normalize_city(deal.origin_city).casefold(),
            _normalize_city(deal.destination_city).casefold(),
            deal.transport_mode.value,
        )
        golden = golden_index.get(key)
        if golden is not None:
            matched.append((golden, deal))
    return matched


def _price_in_reasonable_range(golden: GoldenDeal, deal: Deal) -> bool:
    lower_bound_fen = int(golden.price_range_min * 100 * 0.7)
    upper_bound_fen = int(golden.price_range_max * 100 * 1.3)
    return lower_bound_fen <= deal.price_cny_fen <= upper_bound_fen


def _normalize_city(city: str) -> str:
    return CITY_NORMALIZATION.get(city, city)


def _is_valid_https_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)
