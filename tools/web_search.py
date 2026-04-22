from __future__ import annotations

import asyncio
import json
import logging
from importlib import import_module
from pathlib import Path
from typing import Any

from config import Settings, get_settings
from tools.base import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


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
        max_results = min(max(params.max_results, 5), 10)
        if not self.settings.tavily_api_key:
            logger.warning("TAVILY_API_KEY is not configured; using cached search fallback")
            return ToolOutput(success=True, data=self._fallback_results(params.query, max_results))

        logger.info("Searching Tavily query=%r max_results=%s", params.query, max_results)
        try:
            data = await self._search(params.query, max_results)
        except Exception as exc:
            logger.exception("Tavily search failed for query=%r", params.query)
            return ToolOutput(
                success=True,
                data=self._fallback_results(params.query, max_results, reason=str(exc)),
            )
        return ToolOutput(
            success=True,
            data=self._merge_results(
                primary=data,
                cached=self._cached_results(params.query, max_results),
                max_results=max_results,
            ),
        )

    async def _search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        tavily = import_module("tavily")
        client = tavily.TavilyClient(api_key=self.settings.tavily_api_key)
        response = await asyncio.to_thread(
            client.search,
            query=query,
            max_results=max_results,
            include_answer=True,
        )
        results = response.get("results", []) if isinstance(response, dict) else []
        answer = str(response.get("answer", "")) if isinstance(response, dict) else ""
        normalized = [
            {
                "title": str(item.get("title", "")),
                "url": str(item.get("url", "")),
                "content": str(item.get("content", "")),
            }
            for item in results
            if isinstance(item, dict)
        ]
        if answer and normalized:
            normalized[0]["content"] = f"Tavily answer: {answer}\n{normalized[0]['content']}"
        elif answer:
            normalized.append({"title": "Tavily answer", "url": "", "content": answer})
        logger.info("Tavily returned %s results for query=%r", len(normalized), query)
        return normalized

    def _fallback_results(
        self,
        query: str,
        max_results: int,
        reason: str | None = None,
    ) -> list[dict[str, str]]:
        cached = self._cached_results(query, max_results)
        if cached:
            logger.warning(
                "Using cached web_search fallback for query=%r reason=%s results=%s",
                query,
                reason or "fallback",
                len(cached),
            )
            return cached

        detail = reason or "Tavily is unavailable"
        return [
            {
                "title": "fallback",
                "url": "",
                "content": (
                    f"No cached deal snapshot matched query '{query}'. "
                    f"Reason: {detail}."
                ),
            }
        ]

    def _merge_results(
        self,
        *,
        primary: list[dict[str, Any]],
        cached: list[dict[str, str]],
        max_results: int,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in [*cached, *primary]:
            key = self._result_key(item)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= max_results:
                break
        return merged

    def _cached_results(self, query: str, max_results: int) -> list[dict[str, str]]:
        query_lower = query.casefold()
        snapshots = self._load_cached_deals()
        if not snapshots:
            return []

        scored: list[tuple[int, int, str, dict[str, Any]]] = []
        for snapshot_date, deal in snapshots:
            score = self._deal_match_score(query_lower, deal)
            if score <= 0:
                continue
            scored.append((score, -self._safe_int(deal.get("price_cny_fen")), snapshot_date, deal))

        if not scored:
            latest_date = snapshots[0][0]
            for snapshot_date, deal in snapshots:
                if snapshot_date != latest_date:
                    continue
                scored.append((1, -self._safe_int(deal.get("price_cny_fen")), snapshot_date, deal))

        scored.sort(reverse=True)
        return [
            self._deal_to_search_result(snapshot_date, deal)
            for _, _, snapshot_date, deal in scored[:max_results]
        ]

    def _load_cached_deals(self) -> list[tuple[str, dict[str, Any]]]:
        deals_dir = Path(__file__).resolve().parents[1] / "data" / "deals"
        snapshots: list[tuple[str, dict[str, Any]]] = []
        if not deals_dir.exists():
            return snapshots

        for path in sorted(deals_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed to read cached deals from %s", path)
                continue
            if not isinstance(payload, list):
                continue
            for item in payload:
                if isinstance(item, dict):
                    snapshots.append((path.stem, item))
        return snapshots

    def _deal_match_score(self, query_lower: str, deal: dict[str, Any]) -> int:
        origin_city = str(deal.get("origin_city", "")).casefold()
        destination_city = str(deal.get("destination_city", "")).casefold()
        operator = str(deal.get("operator", "")).casefold()
        transport_mode = str(deal.get("transport_mode", "")).casefold()

        score = 0
        if origin_city and origin_city in query_lower:
            score += 3
        if destination_city and destination_city in query_lower:
            score += 5
        if operator and operator in query_lower:
            score += 2
        if transport_mode == "flight" and any(
            token in query_lower for token in ("flight", "flights", "机票", "航班", "廉航")
        ):
            score += 1
        if any(token in query_lower for token in ("低价", "特价", "cheap", "deal", "旅行", "旅游")):
            score += 1
        return score

    def _deal_to_search_result(self, snapshot_date: str, deal: dict[str, Any]) -> dict[str, str]:
        origin_city = str(deal.get("origin_city", "")).strip() or "unknown"
        destination_city = str(deal.get("destination_city", "")).strip() or "unknown"
        departure_date = str(deal.get("departure_date", "")).strip() or "unknown date"
        operator = str(deal.get("operator", "")).strip() or "unknown operator"
        notes = " ".join(str(deal.get("notes", "")).split())
        price_yuan = max(self._safe_int(deal.get("price_cny_fen")) // 100, 0)
        booking_url = str(deal.get("booking_url", "")).strip()
        source_url = str(deal.get("source_url", "")).strip()
        url = booking_url or source_url

        content = (
            f"Cached local snapshot {snapshot_date}: "
            f"{origin_city}飞{destination_city} {departure_date} 单程 {price_yuan} 元，"
            f"{operator}。"
        )
        if notes:
            content = f"{content} {notes}"

        return {
            "title": f"{origin_city} -> {destination_city} CNY {price_yuan}",
            "url": url,
            "content": content,
        }

    def _result_key(self, item: dict[str, Any]) -> str:
        url = str(item.get("url", "")).strip().casefold()
        if url:
            return url
        title = str(item.get("title", "")).strip().casefold()
        content = str(item.get("content", "")).strip().casefold()
        return f"{title}|{content[:160]}"

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
