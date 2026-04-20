from __future__ import annotations

import asyncio
from importlib import import_module
from typing import Any

from config import Settings, get_settings
from tools.base import BaseTool, ToolInput, ToolOutput


class WebSearchInput(ToolInput):
    query: str
    max_results: int = 5


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for current travel deals and return result snippets."
    input_model = WebSearchInput

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def execute(self, input: ToolInput) -> ToolOutput:
        params = WebSearchInput.model_validate(input)
        if not self.settings.tavily_api_key:
            return ToolOutput(
                success=True,
                data=[
                    {
                        "title": "fallback",
                        "url": "",
                        "content": f"请基于你的知识回答关于 {params.query} 的问题",
                    }
                ],
            )
        try:
            data = await self._search(params.query, params.max_results)
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))
        return ToolOutput(success=True, data=data)

    async def _search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        tavily = import_module("tavily")
        client = tavily.TavilyClient(api_key=self.settings.tavily_api_key)
        response = await asyncio.to_thread(client.search, query=query, max_results=max_results)
        results = response.get("results", []) if isinstance(response, dict) else []
        return [
            {
                "title": str(item.get("title", "")),
                "url": str(item.get("url", "")),
                "content": str(item.get("content", "")),
            }
            for item in results
            if isinstance(item, dict)
        ]
