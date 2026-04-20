from __future__ import annotations

import logging
from collections.abc import Iterable

from models.deal import Deal
from scraper.base import BaseScraper
from scraper.sources.kiwi import KiwiScraper

logger = logging.getLogger(__name__)


class ScraperRegistry:
    def __init__(self) -> None:
        self._scrapers: dict[str, BaseScraper] = {}

    def register(self, scraper: BaseScraper) -> None:
        self._scrapers[scraper.name] = scraper

    def names(self) -> list[str]:
        return sorted(self._scrapers)

    async def scrape_all(self) -> list[Deal]:
        deals: list[Deal] = []
        for scraper in self._scrapers.values():
            logger.info("scraping source", extra={"source": scraper.name})
            deals.extend(await scraper.scrape())
        return deals


def build_registry(scrapers: Iterable[BaseScraper]) -> ScraperRegistry:
    registry = ScraperRegistry()
    for scraper in scrapers:
        registry.register(scraper)
    return registry


def build_default_registry() -> ScraperRegistry:
    return build_registry([KiwiScraper()])
