from __future__ import annotations

from models.deal import Deal
from scraper.base import BaseScraper


class KiwiScraper(BaseScraper):
    name = "kiwi"

    async def scrape(self) -> list[Deal]:
        return []
