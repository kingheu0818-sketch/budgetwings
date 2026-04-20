from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from llm.base import LLMAdapter
from models.deal import Deal, TransportMode
from tools.base import BaseTool, ToolInput, ToolOutput


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
        return [self._deal_from_payload(item) for item in raw_deals if isinstance(item, dict)]

    def _deal_from_payload(self, item: dict[str, Any]) -> Deal:
        price_cny = int(item.get("price_cny", 0))
        departure = item.get("departure_date") or date.today().isoformat()
        transport = item.get("transport_mode", "flight")
        return Deal.model_validate(
            {
                "source": str(item.get("source", "agent")),
                "origin_city": str(item.get("origin_city", "unknown")),
                "origin_code": item.get("origin_code"),
                "destination_city": str(item.get("destination_city", "unknown")),
                "destination_code": item.get("destination_code"),
                "destination_country": item.get("destination_country"),
                "price_cny_fen": price_cny * 100,
                "transport_mode": TransportMode(str(transport)),
                "departure_date": departure,
                "return_date": item.get("return_date"),
                "is_round_trip": bool(item.get("is_round_trip", False)),
                "operator": item.get("operator"),
                "booking_url": str(item.get("booking_url", "https://example.com")),
                "source_url": item.get("source_url"),
                "notes": item.get("notes"),
            }
        )

    def _extract_json(self, response: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
        if fenced:
            return fenced.group(1)
        return response.strip()

    def _system_prompt(self) -> str:
        return (
            "Extract low-price travel deals as strict JSON. Return either a list or "
            "an object with a deals list. Each item must include origin_city, "
            "destination_city, price_cny, transport_mode, departure_date, and booking_url."
        )
