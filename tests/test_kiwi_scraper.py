from __future__ import annotations

from decimal import Decimal

import pytest

from models.deal import TransportMode
from scraper.sources.kiwi import KiwiScraper, KiwiScraperError


def kiwi_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": "deal-1",
        "cityFrom": "Shenzhen",
        "flyFrom": "SZX",
        "cityTo": "Chiang Mai",
        "flyTo": "CNX",
        "countryTo": {"name": "Thailand"},
        "price": 680,
        "currency": "CNY",
        "local_departure": "2026-05-01T08:30:00.000Z",
        "airlines": ["FD"],
        "deep_link": "https://www.kiwi.com/deep-link",
    }
    item.update(overrides)
    return item


def test_parse_deal_maps_kiwi_fields_to_deal() -> None:
    scraper = KiwiScraper()

    deal = scraper.parse_deal(kiwi_item(), origin_city="Shenzhen", origin_code="SZX")

    assert deal.source == "kiwi"
    assert deal.origin_city == "Shenzhen"
    assert deal.origin_code == "SZX"
    assert deal.destination_city == "Chiang Mai"
    assert deal.destination_code == "CNX"
    assert deal.destination_country == "Thailand"
    assert deal.price_cny_fen == 68_000
    assert deal.transport_mode is TransportMode.FLIGHT
    assert deal.departure_date.isoformat() == "2026-05-01"
    assert deal.operator == "FD"
    assert str(deal.booking_url) == "https://www.kiwi.com/deep-link"


def test_parse_deal_converts_non_cny_currency_to_cny_fen() -> None:
    scraper = KiwiScraper(exchange_rates_to_cny={"USD": Decimal("7.20")})

    deal = scraper.parse_deal(
        kiwi_item(price=100, currency="USD"),
        origin_city="Shenzhen",
        origin_code="SZX",
    )

    assert deal.price_cny_fen == 72_000


def test_parse_response_filters_prices_at_or_above_threshold() -> None:
    scraper = KiwiScraper()
    payload = {
        "data": [
            kiwi_item(id="cheap", price=1499),
            kiwi_item(id="too-expensive", price=1500),
        ]
    }

    deals = scraper.parse_response(payload, origin_city="Shenzhen", origin_code="SZX")

    assert len(deals) == 1
    assert deals[0].price_cny_fen == 149_900


def test_parse_response_skips_invalid_items() -> None:
    scraper = KiwiScraper()
    payload = {"data": [kiwi_item(), kiwi_item(id="bad", deep_link=None)]}

    deals = scraper.parse_response(payload, origin_city="Shenzhen", origin_code="SZX")

    assert len(deals) == 1
    assert deals[0].destination_city == "Chiang Mai"


def test_parse_deal_raises_for_unsupported_currency() -> None:
    scraper = KiwiScraper(exchange_rates_to_cny={"CNY": Decimal("1")})

    with pytest.raises(KiwiScraperError, match="unsupported Kiwi currency"):
        scraper.parse_deal(
            kiwi_item(price=100, currency="MARS"),
            origin_city="Shenzhen",
            origin_code="SZX",
        )


def test_build_search_params_uses_anywhere_and_required_window() -> None:
    scraper = KiwiScraper()

    params = scraper._build_search_params("SZX")

    assert params["fly_from"] == "SZX"
    assert params["fly_to"] == "anywhere"
    assert params["flight_type"] == "oneway"
    assert params["curr"] == "CNY"
    assert params["price_to"] == 1500
