from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from config import Settings, get_settings
from tools.base import BaseTool, ToolInput, ToolOutput


class WebFetchInput(ToolInput):
    url: str
    max_chars: int = 8000


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "Fetch a web page and extract readable text content."
    input_model = WebFetchInput

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def execute(self, input: ToolInput) -> ToolOutput:
        params = WebFetchInput.model_validate(input)
        try:
            html = await self._fetch_html(params.url)
            text = self._extract_text(html, params.max_chars)
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))
        return ToolOutput(success=True, data={"url": params.url, "text": text})

    async def _fetch_html(self, url: str) -> str:
        headers = {"User-Agent": self.settings.user_agent}
        timeout = httpx.Timeout(self.settings.scraper_timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _extract_text(self, html: str, max_chars: int) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:max_chars]
