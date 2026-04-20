from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Destination(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str = Field(min_length=1)
    country: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class VisaInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    cn_passport: str = Field(min_length=1)
    tips: str | None = None


class WeatherInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    best_months: list[int] = Field(default_factory=list)
    rainy_season: list[int] = Field(default_factory=list)
    current: str | None = None

    @field_validator("best_months", "rainy_season")
    @classmethod
    def validate_months(cls, values: list[int]) -> list[int]:
        invalid_months = [month for month in values if month < 1 or month > 12]
        if invalid_months:
            msg = "months must be between 1 and 12"
            raise ValueError(msg)
        return values


class TransportInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_airport: str | None = None
    in_city: str | None = None


class Highlights(BaseModel):
    model_config = ConfigDict(frozen=True)

    free: list[str] = Field(default_factory=list)
    paid: list[str] = Field(default_factory=list)


class FoodRecommendations(BaseModel):
    model_config = ConfigDict(frozen=True)

    budget: list[str] = Field(default_factory=list)
    midrange: list[str] = Field(default_factory=list)


class AccommodationRecommendations(BaseModel):
    model_config = ConfigDict(frozen=True)

    budget: str | None = None
    midrange: str | None = None


class GuideTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    destination: Destination
    visa: VisaInfo
    weather: WeatherInfo
    transport: TransportInfo
    highlights: Highlights
    food: FoodRecommendations
    accommodation: AccommodationRecommendations
    itinerary_templates: dict[str, dict[str, str]] = Field(default_factory=dict)
    budget_estimate: dict[str, str] = Field(default_factory=dict)

    @field_validator("itinerary_templates")
    @classmethod
    def require_named_days(cls, templates: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        for template_name, days in templates.items():
            if not template_name:
                msg = "itinerary template names must not be empty"
                raise ValueError(msg)
            if not days:
                msg = "itinerary templates must contain at least one day"
                raise ValueError(msg)
        return templates
