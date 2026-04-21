from __future__ import annotations

import logging
from datetime import date, timedelta
from time import perf_counter
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from llm.base import ChatMessage, LLMAdapter
from models.deal import Deal, TransportMode
from tools.base import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)

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


class ExtractedDeal(BaseModel):
    """Intermediate schema exposed to LLM for structured extraction.

    Deliberately simpler than models.Deal: uses yuan not fen, uses strings
    for dates the LLM will format, and exposes fields the LLM can actually
    fill from Tavily snippets.
    """

    model_config = ConfigDict(extra="forbid")

    origin_city: str = Field(..., description="出发城市中文名,如 '深圳'")
    destination_city: str = Field(..., description="目的地城市中文名,如 '曼谷'")
    price_cny: int = Field(
        ...,
        ge=0,
        description="单程票价(元人民币),必须来源于原文中明确出现的数字",
    )
    transport_mode: Literal["flight", "train", "bus", "carpool"]
    departure_date: str = Field(..., description="YYYY-MM-DD 格式,必须是今天之后的未来日期")
    return_date: str | None = None
    is_round_trip: bool = False
    operator: str | None = Field(None, description="航司/铁路/大巴公司,如'春秋航空'")
    booking_url: str | None = None
    source_url: str | None = None
    evidence_text: str | None = Field(
        None,
        description="支撑价格结论的原文证据片段,应包含明确价格数字与路线信息",
    )


class ExtractedDealList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deals: list[ExtractedDeal]


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

        tracer = getattr(self.llm, "tracer", None)
        span_id: str | None = None
        started_at = perf_counter()
        if tracer is not None:
            span_id = tracer.start_span(
                tracer.current_trace_id,
                "price_parser.execute",
                {
                    "origin_city": params.origin_city,
                    "max_price_cny": params.max_price_cny,
                    "text_preview": params.text[:500],
                },
            )

        llm_structured_call_ok = False
        pydantic_validation_ok = False
        pydantic_error_count = 0
        deals: list[Deal] = []
        evidence_missing_count = 0
        output: ToolOutput

        try:
            payload = await self.llm.extract_structured(
                self._messages(params),
                schema=ExtractedDealList.model_json_schema(),
                schema_name="deal_list",
                schema_description=(
                    "Extract low-price travel deals from noisy web snippets as strict JSON."
                ),
            )
            llm_structured_call_ok = True
            extracted = ExtractedDealList.model_validate(payload)
            pydantic_validation_ok = True
            evidence_missing_count = sum(
                1 for item in extracted.deals if not (item.evidence_text or "").strip()
            )
            extracted_deals = [
                self._deal_from_extracted(item, params.origin_city, params.max_price_cny)
                for item in extracted.deals
            ]
            deals = [deal for deal in extracted_deals if deal is not None]
            output = ToolOutput(success=True, data=[deal.model_dump(mode="json") for deal in deals])
        except ValidationError as exc:
            pydantic_error_count = len(exc.errors())
            output = ToolOutput(success=False, error=str(exc))
        except Exception as exc:
            output = ToolOutput(success=False, error=str(exc))

        logger.info(
            "price_parser result",
            extra={
                "samples_in": 1,
                "deals_out": len(deals),
                "llm_structured_call_ok": llm_structured_call_ok,
                "pydantic_validation_ok": pydantic_validation_ok,
                "pydantic_error_count": pydantic_error_count,
                "evidence_missing_count": evidence_missing_count,
            },
        )
        if tracer is not None and span_id is not None:
            tracer.end_span(
                span_id,
                output_data={
                    "success": output.success,
                    "deals_out": len(deals),
                    "error": output.error,
                },
                duration_ms=(perf_counter() - started_at) * 1000,
            )
        return output

    def _messages(self, params: PriceParserInput) -> list[ChatMessage]:
        return [
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

    def _deal_from_extracted(
        self,
        item: ExtractedDeal,
        origin_city_hint: str | None,
        max_price_cny: int,
    ) -> Deal | None:
        if item.price_cny <= 0 or item.price_cny > max_price_cny:
            return None
        origin_city = (item.origin_city or origin_city_hint or "unknown").strip() or "unknown"
        destination_city = item.destination_city.strip() or "unknown"
        return_date = self._return_date(item.return_date, item.departure_date, item.is_round_trip)
        payload = {
            "source": "agent",
            "origin_city": origin_city,
            "origin_code": None,
            "destination_city": destination_city,
            "destination_code": None,
            "destination_country": None,
            "price_cny_fen": item.price_cny * 100,
            "transport_mode": self._transport_mode(item.transport_mode),
            "departure_date": self._departure_date(item.departure_date),
            "return_date": return_date,
            "is_round_trip": item.is_round_trip,
            "operator": item.operator,
            "booking_url": self._booking_url(item, origin_city, destination_city),
            "source_url": item.source_url,
            "notes": None,
        }
        return Deal.model_validate(payload)

    def _transport_mode(self, value: Any) -> TransportMode:
        try:
            return TransportMode(str(value).lower())
        except ValueError:
            return TransportMode.FLIGHT

    def _booking_url(
        self,
        item: ExtractedDeal,
        origin_city: str,
        destination_city: str,
    ) -> str:
        booking_url = (item.booking_url or "").strip()
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

    def _return_date(
        self,
        value: str | None,
        departure_value: str,
        is_round_trip: bool,
    ) -> str | None:
        if not is_round_trip:
            return None
        departure = date.fromisoformat(self._departure_date(departure_value))
        if value is None:
            return (departure + timedelta(days=2)).isoformat()
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            parsed = departure + timedelta(days=2)
        if parsed < departure:
            parsed = departure + timedelta(days=2)
        return parsed.isoformat()

    def _system_prompt(self) -> str:
        return (
            "Extract low-price travel deals as strict structured data. "
            "Only include deals with an explicit numeric price stated in the source text. "
            "Do not estimate, infer, or invent a price. "
            "If no valid deal exists, return an empty deals list. "
            "Prefer direct booking URLs when present; otherwise include the most relevant "
            "route URL. "
            "Fill evidence_text with the shortest quote-like snippet that proves the route "
            "and price. "
            f"Today is {date.today().isoformat()}; departure_date must be a future ISO date."
        )
