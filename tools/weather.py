from __future__ import annotations

from typing import Any

import httpx

from tools.base import BaseTool, ToolInput, ToolOutput


class WeatherInput(ToolInput):
    city: str
    country: str | None = None
    days: int = 7


class WeatherTool(BaseTool):
    name = "weather_lookup"
    description = "Look up destination weather using the free Open-Meteo API."
    input_model = WeatherInput

    async def execute(self, input: ToolInput) -> ToolOutput:
        params = WeatherInput.model_validate(input)
        try:
            data = await self._lookup(params.city, params.country, params.days)
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))
        return ToolOutput(success=True, data=data)

    async def _lookup(self, city: str, country: str | None, days: int) -> dict[str, Any]:
        query = f"{city} {country or ''}".strip()
        async with httpx.AsyncClient(timeout=15) as client:
            geo = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 1, "language": "en", "format": "json"},
            )
            geo.raise_for_status()
            geo_payload = geo.json()
            results = geo_payload.get("results", []) if isinstance(geo_payload, dict) else []
            if not results:
                msg = f"destination not found: {query}"
                raise ValueError(msg)
            location = results[0]
            forecast = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "forecast_days": days,
                    "timezone": "auto",
                },
            )
            forecast.raise_for_status()
        return {
            "city": location.get("name", city),
            "country": location.get("country"),
            "forecast": forecast.json().get("daily", {}),
        }
