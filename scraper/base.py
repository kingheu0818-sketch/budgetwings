from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from config import Settings, get_settings
from models.deal import Deal


class ScraperRequestError(RuntimeError):
    pass


class BaseScraper(ABC):
    name: str

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._last_request_at: float | None = None

    @abstractmethod
    async def scrape(self) -> list[Deal]:
        """Return normalized travel deals from this data source."""

    async def request_json(self, method: str, url: str, **kwargs: Any) -> object:
        response = await self.request(method, url, **kwargs)
        return response.json()

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        await self._respect_rate_limit()

        request_headers = {"User-Agent": self.settings.user_agent}
        extra_headers = kwargs.pop("headers", None)
        if isinstance(extra_headers, dict):
            request_headers.update({str(key): str(value) for key, value in extra_headers.items()})

        timeout = httpx.Timeout(self.settings.scraper_timeout_seconds)
        last_error: Exception | None = None

        for attempt in range(1, self.settings.scraper_retry_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout, headers=request_headers) as client:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    self._last_request_at = time.monotonic()
                    return response
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= self.settings.scraper_retry_attempts:
                    break
                await asyncio.sleep(self.settings.scraper_retry_backoff_seconds * attempt)

        msg = f"{self.name} request failed after {self.settings.scraper_retry_attempts} attempts"
        raise ScraperRequestError(msg) from last_error

    async def _respect_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait_seconds = self.settings.request_rate_limit_seconds - elapsed
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
