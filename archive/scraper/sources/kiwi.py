from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import ValidationError

from config import Settings
from models.deal import Deal, TransportMode
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)

KIWI_SEARCH_URL = "https://tequila-api.kiwi.com/v2/search"
DEFAULT_ORIGIN_CITIES: dict[str, str] = {
    "Beijing": "BJS",
    "Shanghai": "SHA",
    "Guangzhou": "CAN",
    "Shenzhen": "SZX",
    "Chengdu": "CTU",
    "Hangzhou": "HGH",
}
DEFAULT_EXCHANGE_RATES_TO_CNY: dict[str, Decimal] = {
    "CNY": Decimal("1"),
    "USD": Decimal("7.20"),
    "EUR": Decimal("7.80"),
    "HKD": Decimal("0.92"),
    "JPY": Decimal("0.05"),
    "KRW": Decimal("0.0052"),
    "THB": Decimal("0.20"),
    "SGD": Decimal("5.35"),
}
MAX_ONE_WAY_PRICE_CNY_FEN = 150_000


class KiwiScraperError(RuntimeError):
    pass


class KiwiScraper(BaseScraper):
    name = "kiwi"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        origin_cities: dict[str, str] | None = None,
        destination: str = "anywhere",
        exchange_rates_to_cny: dict[str, Decimal] | None = None,
    ) -> None:
        super().__init__(settings=settings)
        self.origin_cities = origin_cities or DEFAULT_ORIGIN_CITIES
        self.destination = destination
        self.exchange_rates_to_cny = exchange_rates_to_cny or DEFAULT_EXCHANGE_RATES_TO_CNY

    async def scrape(self) -> list[Deal]:
        if not self.settings.kiwi_api_key:
            msg = "KIWI_API_KEY is required to run KiwiScraper"
            raise KiwiScraperError(msg)

        deals: list[Deal] = []
        for origin_city, origin_code in self.origin_cities.items():
            payload = await self.request_json(
                "GET",
                KIWI_SEARCH_URL,
                headers={"apikey": self.settings.kiwi_api_key},
                params=self._build_search_params(origin_code),
            )
            deals.extend(
                self.parse_response(payload, origin_city=origin_city, origin_code=origin_code)
            )
        return deals

    def _build_search_params(
        self,
        origin_code: str,
        today: date | None = None,
    ) -> dict[str, str | int]:
        base_date = today or date.today()
        start_date = base_date + timedelta(days=7)
        end_date = base_date + timedelta(days=60)
        return {
            "fly_from": origin_code,
            "fly_to": self.destination,
            "date_from": start_date.strftime("%d/%m/%Y"),
            "date_to": end_date.strftime("%d/%m/%Y"),
            "flight_type": "oneway",
            "curr": "CNY",
            "price_to": 1500,
            "partner_market": "cn",
            "sort": "price",
            "limit": 50,
            "one_for_city": 1,
        }

    def parse_response(self, payload: object, *, origin_city: str, origin_code: str) -> list[Deal]:
        if not isinstance(payload, dict):
            msg = "Kiwi response must be a JSON object"
            raise KiwiScraperError(msg)

        raw_items = payload.get("data", [])
        if not isinstance(raw_items, list):
            msg = "Kiwi response data field must be a list"
            raise KiwiScraperError(msg)

        deals: list[Deal] = []
        for item in raw_items:
            if not isinstance(item, dict):
                logger.warning("skipping non-object Kiwi item", extra={"source": self.name})
                continue
            try:
                deal = self.parse_deal(item, origin_city=origin_city, origin_code=origin_code)
            except (KiwiScraperError, ValidationError, ValueError):
                logger.warning(
                    "skipping invalid Kiwi item",
                    extra={"source": self.name, "item_id": item.get("id")},
                    exc_info=True,
                )
                continue
            if deal.price_cny_fen < MAX_ONE_WAY_PRICE_CNY_FEN:
                deals.append(deal)
        return deals

    def parse_deal(self, item: dict[str, Any], *, origin_city: str, origin_code: str) -> Deal:
        price_cny_fen = self._price_to_cny_fen(item)
        departure_date = self._parse_departure_date(item)

        destination_city = self._required_str(item, "cityTo")
        destination_code = self._optional_str(item, "flyTo") or self._optional_str(
            item,
            "cityCodeTo",
        )
        booking_url = self._optional_str(item, "deep_link")
        if booking_url is None:
            msg = "Kiwi deal is missing deep_link"
            raise KiwiScraperError(msg)

        return Deal.model_validate(
            {
                "source": self.name,
                "origin_city": origin_city or self._optional_str(item, "cityFrom") or origin_code,
                "origin_code": self._optional_str(item, "flyFrom") or origin_code,
                "destination_city": destination_city,
                "destination_code": destination_code,
                "destination_country": self._destination_country(item),
                "price_cny_fen": price_cny_fen,
                "transport_mode": TransportMode.FLIGHT,
                "departure_date": departure_date,
                "is_round_trip": False,
                "operator": self._operator(item),
                "booking_url": booking_url,
                "scraped_at": datetime.now(UTC),
                "notes": "Kiwi Tequila anywhere search",
            }
        )

    def _price_to_cny_fen(self, item: dict[str, Any]) -> int:
        price = item.get("price")
        if not isinstance(price, int | float | Decimal):
            msg = "Kiwi deal is missing numeric price"
            raise KiwiScraperError(msg)

        currency = str(item.get("currency") or item.get("curr") or "CNY").upper()
        rate = self.exchange_rates_to_cny.get(currency)
        if rate is None:
            msg = f"unsupported Kiwi currency: {currency}"
            raise KiwiScraperError(msg)

        cny = Decimal(str(price)) * rate
        return int((cny * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def _parse_departure_date(self, item: dict[str, Any]) -> date:
        local_departure = self._optional_str(item, "local_departure")
        if local_departure:
            return datetime.fromisoformat(local_departure.replace("Z", "+00:00")).date()

        departure_timestamp = item.get("dTimeUTC") or item.get("dTime")
        if isinstance(departure_timestamp, int | float):
            return datetime.fromtimestamp(departure_timestamp, tz=UTC).date()

        msg = "Kiwi deal is missing departure time"
        raise KiwiScraperError(msg)

    def _operator(self, item: dict[str, Any]) -> str | None:
        airlines = item.get("airlines")
        if isinstance(airlines, list) and airlines:
            return ",".join(str(airline) for airline in airlines)
        return self._optional_str(item, "airline")

    def _destination_country(self, item: dict[str, Any]) -> str | None:
        country_to = item.get("countryTo")
        if isinstance(country_to, dict):
            name = country_to.get("name")
            if isinstance(name, str):
                return name
        return None

    def _required_str(self, item: dict[str, Any], key: str) -> str:
        value = self._optional_str(item, key)
        if value is None:
            msg = f"Kiwi deal is missing {key}"
            raise KiwiScraperError(msg)
        return value

    def _optional_str(self, item: dict[str, Any], key: str) -> str | None:
        value = item.get(key)
        if value is None:
            return None
        return str(value)
