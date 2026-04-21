from __future__ import annotations

from models.deal import Deal
from scraper.base import BaseScraper


class SkyscannerScraper(BaseScraper):
    name = "skyscanner"

    async def scrape(self) -> list[Deal]:
        return []
