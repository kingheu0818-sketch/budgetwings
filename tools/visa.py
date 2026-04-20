from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.base import BaseTool, ToolInput, ToolOutput


class VisaLookupInput(ToolInput):
    destination_city: str | None = None
    destination_country: str
    passport_country: str = "CN"


class VisaTool(BaseTool):
    name = "visa_lookup"
    description = "Look up visa policy from the local BudgetWings visa database."
    input_model = VisaLookupInput

    def __init__(self, data_path: Path = Path("data/visa_policies.json")) -> None:
        self.data_path = data_path

    async def execute(self, input: ToolInput) -> ToolOutput:
        params = VisaLookupInput.model_validate(input)
        try:
            policy = self.lookup(params.destination_country, params.destination_city)
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))
        return ToolOutput(success=True, data=policy)

    def lookup(self, country: str, city: str | None = None) -> dict[str, Any]:
        policies = json.loads(self.data_path.read_text(encoding="utf-8"))
        country_key = country.casefold()
        city_key = city.casefold() if city else None
        for policy in policies:
            policy_country = str(policy.get("country", "")).casefold()
            policy_city = str(policy.get("city", "")).casefold()
            if policy_country == country_key and (city_key is None or policy_city == city_key):
                return dict(policy)
        return {
            "country": country,
            "city": city,
            "visa_type": "unknown",
            "summary": "No local visa policy entry yet. Verify official sources before booking.",
        }
