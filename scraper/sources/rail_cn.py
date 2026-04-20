from __future__ import annotations

from models.deal import Deal
from scraper.base import BaseScraper


class ChinaRailScraper(BaseScraper):
    name = "rail_cn"

    async def scrape(self) -> list[Deal]:
        return []
