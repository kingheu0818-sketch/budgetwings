from __future__ import annotations

from datetime import UTC, date, datetime

from models.deal import Deal, TransportMode
from models.guide import GuideTemplate
from models.persona import PersonaType, default_persona_filter


def test_deal_stores_price_in_cny_fen() -> None:
    deal = Deal.model_validate(
        {
            "source": "example",
            "origin_city": "Shenzhen",
            "origin_code": "SZX",
            "destination_city": "Chiang Mai",
            "destination_code": "CNX",
            "price_cny_fen": 68_000,
            "transport_mode": TransportMode.FLIGHT,
            "departure_date": date(2026, 5, 1),
            "return_date": date(2026, 5, 3),
            "is_round_trip": True,
            "operator": "Example Air",
            "booking_url": "https://example.com/book",
            "scraped_at": datetime(2026, 4, 20, tzinfo=UTC),
        }
    )

    assert deal.price_cny_fen == 68_000
    assert deal.transport_mode is TransportMode.FLIGHT


def test_default_persona_filter_values() -> None:
    worker = default_persona_filter(PersonaType.WORKER)
    student = default_persona_filter(PersonaType.STUDENT)

    assert worker.max_one_way_price_cny_fen == 150_000
    assert worker.default_sort == "date"
    assert student.max_one_way_price_cny_fen == 50_000
    assert student.default_sort == "price"


def test_guide_template_matches_prd_shape() -> None:
    template = GuideTemplate.model_validate(
        {
            "destination": {"city": "Chiang Mai", "country": "Thailand", "tags": ["food"]},
            "visa": {"cn_passport": "Visa on arrival", "tips": "Check official policy"},
            "weather": {"best_months": [11, 12, 1, 2], "rainy_season": [6, 7, 8, 9]},
            "transport": {"from_airport": "Songthaew", "in_city": "Walk and ride"},
            "highlights": {"free": ["Old City"], "paid": ["Doi Suthep"]},
            "food": {"budget": ["Night market"], "midrange": ["Cafe"]},
            "accommodation": {"budget": "Hostel", "midrange": "Guesthouse"},
            "itinerary_templates": {"2day": {"day1": "Temples", "day2": "Return"}},
            "budget_estimate": {"student_2day": "CNY 300-500"},
        }
    )

    assert template.destination.city == "Chiang Mai"
    assert template.itinerary_templates["2day"]["day1"] == "Temples"
