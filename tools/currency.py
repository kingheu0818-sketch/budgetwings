from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from tools.base import BaseTool, ToolInput, ToolOutput

FALLBACK_RATES_TO_CNY: dict[str, Decimal] = {
    "CNY": Decimal("1"),
    "USD": Decimal("7.20"),
    "EUR": Decimal("7.80"),
    "HKD": Decimal("0.92"),
    "JPY": Decimal("0.05"),
    "KRW": Decimal("0.0052"),
    "THB": Decimal("0.20"),
    "SGD": Decimal("5.35"),
    "MYR": Decimal("1.55"),
    "PHP": Decimal("0.13"),
}


class CurrencyConvertInput(ToolInput):
    amount: float
    from_currency: str
    to_currency: str = "CNY"


class CurrencyTool(BaseTool):
    name = "currency_convert"
    description = "Convert money between currencies with remote rates and fixed fallback rates."
    input_model = CurrencyConvertInput

    async def execute(self, input: ToolInput) -> ToolOutput:
        params = CurrencyConvertInput.model_validate(input)
        try:
            converted = await self.convert(
                Decimal(str(params.amount)),
                params.from_currency.upper(),
                params.to_currency.upper(),
            )
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))
        return ToolOutput(
            success=True,
            data={"amount": float(converted), "currency": params.to_currency},
        )

    async def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        rates = await self._fetch_rates_to_cny()
        source_rate = rates.get(from_currency)
        target_rate = rates.get(to_currency)
        if source_rate is None or target_rate is None:
            rates = FALLBACK_RATES_TO_CNY
            source_rate = rates.get(from_currency)
            target_rate = rates.get(to_currency)
        if source_rate is None or target_rate is None:
            msg = f"unsupported currency pair: {from_currency}/{to_currency}"
            raise ValueError(msg)
        cny_amount = amount * source_rate
        return (cny_amount / target_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    async def _fetch_rates_to_cny(self) -> dict[str, Decimal]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://open.er-api.com/v6/latest/CNY")
                response.raise_for_status()
                payload: Any = response.json()
            rates = payload.get("rates", {}) if isinstance(payload, dict) else {}
            if not isinstance(rates, dict):
                return FALLBACK_RATES_TO_CNY
            return {
                code: Decimal("1") / Decimal(str(rate))
                for code, rate in rates.items()
                if isinstance(code, str) and isinstance(rate, int | float)
            } | {"CNY": Decimal("1")}
        except Exception:
            return FALLBACK_RATES_TO_CNY
