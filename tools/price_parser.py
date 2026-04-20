from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from llm.base import LLMAdapter
from models.deal import Deal, TransportMode
from tools.base import BaseTool, ToolInput, ToolOutput

CITY_ROUTE_CODES: dict[str, str] = {
    "北京": "bjs",
    "上海": "sha",
    "广州": "can",
    "深圳": "szx",
    "成都": "ctu",
    "杭州": "hgh",
    "曼谷": "bkk",
    "清迈": "cnx",
    "东京": "tyo",
    "大阪": "kix",
    "首尔": "sel",
    "海口": "hak",
    "湛江": "zha",
    "南宁": "nng",
    "贵阳": "kwe",
    "重庆": "ckg",
}


class PriceParserInput(ToolInput):
    text: str
    origin_city: str | None = None
    max_price_cny: int = 1500


class PriceParserTool(BaseTool):
    name = "price_parser"
    description = "Extract structured low-price travel deals from unstructured web text."
    input_model = PriceParserInput

    def __init__(self, llm: LLMAdapter | None = None) -> None:
        self.llm = llm

    async def execute(self, input: ToolInput) -> ToolOutput:
        params = PriceParserInput.model_validate(input)
        if self.llm is None:
            return ToolOutput(success=False, error="LLM adapter is required for price_parser")
        try:
            response = await self.llm.chat(
                [
                    {"role": "system", "content": self._system_prompt()},
                    {
                        "role": "user",
                        "content": (
                            f"Origin city: {params.origin_city or 'unknown'}\n"
                            f"Max one-way price CNY: {params.max_price_cny}\n\n"
                            f"{params.text}"
                        ),
                    },
                ]
            )
            deals = self.parse_llm_output(response)
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))
        return ToolOutput(success=True, data=[deal.model_dump(mode="json") for deal in deals])

    def parse_llm_output(self, response: str) -> list[Deal]:
        payload = json.loads(self._extract_json(response))
        raw_deals = payload.get("deals", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_deals, list):
            msg = "price parser expected a JSON list or object with deals"
            raise ValueError(msg)
        deals: list[Deal] = []
        for item in raw_deals:
            if not isinstance(item, dict):
                continue
            deal = self._deal_from_payload(item)
            if deal is not None:
                deals.append(deal)
        return deals

    def _deal_from_payload(self, item: dict[str, Any]) -> Deal | None:
        price_cny = self._price_cny(item.get("price_cny"))
        if price_cny is None or price_cny <= 0:
            return None
        origin_city = str(item.get("origin_city", "unknown"))
        destination_city = str(item.get("destination_city", "unknown"))
        departure = self._departure_date(item.get("departure_date"))
        transport = self._transport_mode(item.get("transport_mode", "flight"))
        return Deal.model_validate(
            {
                "source": str(item.get("source", "agent")),
                "origin_city": origin_city,
                "origin_code": item.get("origin_code"),
                "destination_city": destination_city,
                "destination_code": item.get("destination_code"),
                "destination_country": item.get("destination_country"),
                "price_cny_fen": price_cny * 100,
                "transport_mode": transport,
                "departure_date": departure,
                "return_date": item.get("return_date"),
                "is_round_trip": bool(item.get("is_round_trip", False)),
                "operator": item.get("operator"),
                "booking_url": self._booking_url(item, origin_city, destination_city),
                "source_url": item.get("source_url"),
                "notes": item.get("notes"),
            }
        )

    def _transport_mode(self, value: Any) -> TransportMode:
        try:
            return TransportMode(str(value).lower())
        except ValueError:
            return TransportMode.FLIGHT

    def _price_cny(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return int(value)
        text = str(value).strip()
        if not text or "需确认" in text:
            return None
        match = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
        return int(float(match.group(0))) if match else None

    def _booking_url(
        self,
        item: dict[str, Any],
        origin_city: str,
        destination_city: str,
    ) -> str:
        booking_url = str(item.get("booking_url") or "").strip()
        fallback = self._route_search_url(origin_city, destination_city)
        if not booking_url:
            return fallback or "https://example.com"
        if fallback and self._is_generic_booking_url(booking_url):
            return fallback
        return booking_url

    def _route_search_url(self, origin_city: str, destination_city: str) -> str | None:
        origin = CITY_ROUTE_CODES.get(origin_city)
        destination = CITY_ROUTE_CODES.get(destination_city)
        if origin is None or destination is None:
            return None
        return f"https://www.skyscanner.com.cn/transport/flights/{origin}/{destination}/"

    def _is_generic_booking_url(self, booking_url: str) -> bool:
        parsed = urlparse(booking_url)
        path = parsed.path.strip("/").casefold()
        if not parsed.netloc:
            return True
        if path in {"", "flights", "transport/flights"}:
            return True
        generic_markers = ("airline", "from.html", "routes/szx/cn")
        return any(marker in path for marker in generic_markers)

    def _departure_date(self, value: Any) -> str:
        today = date.today()
        try:
            parsed = date.fromisoformat(str(value))
        except ValueError:
            parsed = today + timedelta(days=14)
        if parsed < today:
            parsed = today + timedelta(days=14)
        return parsed.isoformat()

    def _extract_json(self, response: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
        if fenced:
            return fenced.group(1)
        return response.strip()

    def _system_prompt(self) -> str:
        return (
            "Extract low-price travel deals as strict JSON. Return either a list or "
            "an object with a deals list. Each item must include origin_city, "
            "destination_city, price_cny, transport_mode, departure_date, and booking_url. "
            "Only extract deals that include an explicit numeric price in the source text; "
            "do not estimate or invent prices. If a source has no concrete price, omit it "
            "or mark it as 需确认 outside the deals list. Include airline/operator and "
            "source_url when available. "
            f"Today is {date.today().isoformat()}; departure_date must be a future ISO date."
        )
