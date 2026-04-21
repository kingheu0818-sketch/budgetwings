from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScrapeSchedule:
    hour_utc: int
    minute_utc: int = 0


DEFAULT_SCRAPE_SCHEDULES: tuple[ScrapeSchedule, ...] = (
    ScrapeSchedule(hour_utc=0),
    ScrapeSchedule(hour_utc=12),
)
