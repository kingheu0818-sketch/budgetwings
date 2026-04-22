from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from engine.deal_ranker import rank_deals
from models.deal import Deal
from models.persona import PersonaType, default_persona_filter

DEALS_DIR = Path("data/deals")
logger = logging.getLogger(__name__)


def latest_deals_file(deals_dir: Path = DEALS_DIR) -> Path | None:
    files = list(deals_dir.glob("*.json"))
    if not files:
        return None
    return max(files, key=_deals_file_sort_key)


def load_latest_deals(deals_dir: Path = DEALS_DIR) -> list[Deal]:
    path = latest_deals_file(deals_dir)
    if path is None:
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read local deals from %s: %s", path, exc)
        return []
    if not isinstance(payload, list):
        return []

    deals: list[Deal] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            deals.append(Deal.model_validate(item))
        except ValueError as exc:
            logger.warning("Skipping invalid deal in %s: %s", path, exc)
    return deals


def ranked_deals(persona_type: PersonaType, deals: list[Deal] | None = None) -> list[Deal]:
    source_deals = deals if deals is not None else load_latest_deals()
    return rank_deals(source_deals, default_persona_filter(persona_type))


def search_deals(
    destination: str,
    persona_type: PersonaType,
    deals: list[Deal] | None = None,
) -> list[Deal]:
    normalized = destination.casefold()
    return [
        deal
        for deal in ranked_deals(persona_type, deals)
        if normalized in deal.destination_city.casefold()
        or (deal.destination_country and normalized in deal.destination_country.casefold())
    ]


def deals_within_budget(
    total_budget_yuan: int,
    persona_type: PersonaType,
    deals: list[Deal] | None = None,
) -> list[Deal]:
    budget_fen = total_budget_yuan * 100
    return [deal for deal in ranked_deals(persona_type, deals) if deal.price_cny_fen <= budget_fen]


def format_deal_message(deal: Deal) -> str:
    price_yuan = deal.price_cny_fen // 100
    trip_type = "往返" if deal.is_round_trip else "单程"
    if deal.return_date is not None:
        date_label = f"{deal.departure_date.isoformat()} ~ {deal.return_date.isoformat()}"
    else:
        date_label = deal.departure_date.isoformat()
    return (
        f"✈️ {deal.origin_city} → {deal.destination_city}\n"
        f"💰 ¥{price_yuan} {trip_type}\n"
        f"📅 {date_label}\n"
        f"🔗 订票链接：{deal.booking_url}"
    )


def _deals_file_sort_key(path: Path) -> tuple[datetime, str]:
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 3:
        date_part = parts[0]
        time_part = parts[-1]
        try:
            return datetime.strptime(f"{date_part}_{time_part}", "%Y-%m-%d_%H%M%S"), stem
        except ValueError:
            pass
    try:
        return datetime.strptime(stem, "%Y-%m-%d"), stem
    except ValueError:
        return datetime.min, stem
