from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Any, Literal

from agents.base import BaseAgent
from llm.base import ChatMessage, ToolCallResult, ToolSchema
from models.deal import Deal
from tools.base import BaseTool, ToolOutput
from tools.destinations import DESTINATION_ALIASES
from tools.evidence_validator import EvidenceValidator
from tools.price_parser import ExtractedDeal, PriceParserInput, PriceParserTool
from tools.web_fetch import WebFetchInput
from tools.web_search import WebSearchInput

logger = logging.getLogger(__name__)

ScoutMode = Literal["legacy", "agentic"]

AGENTIC_SCOUT_SYSTEM_PROMPT = """\
You are Scout, an AI agent specialized in finding low-price travel deals.

Your goal: find real, currently-available low-price travel options from {origin_city}
within the next {days} days, with one-way price under CNY {max_price}.

You have four tools:
- web_search: search the web (use Chinese queries for mainland routes, English for overseas)
- web_fetch: read full content of a URL (use only if search snippets are insufficient)
- submit_deal: submit a verified deal (this is the only way to produce output)
- finish: stop the agent loop

Workflow:
1. Plan 2-3 diverse search queries to discover candidate destinations and prices
2. Execute searches, identify promising results
3. If a search result has a concrete numeric price and clear destination, you can
   submit_deal directly
4. If details are ambiguous, use web_fetch to read the full page before submitting
5. After submitting 3-10 deals or exhausting good candidates, call finish

Critical rules:
- NEVER invent prices. Every submit_deal must include `evidence_text` that is an
  EXACT contiguous quote from a web_search or web_fetch result, containing the
  price number and destination name.
- NEVER submit the same origin+destination+date twice
- Prefer deals with explicit departure dates and operator names
- Call finish when you have 3-8 good deals, or when further searches stop finding new destinations
- Respect the budget: you have at most {max_tool_calls} tool calls total

Your output is evaluated on: deal quality (grounded in real evidence),
destination diversity (not all same city), and efficiency (fewer redundant tool
calls is better).
"""


@dataclass(frozen=True)
class AgenticBudget:
    max_iterations: int
    max_tool_calls: int
    max_total_tokens: int = 12_000

    def exhausted(self, iteration: int, tool_calls: int, total_tokens: int) -> bool:
        return (
            iteration >= self.max_iterations
            or tool_calls >= self.max_tool_calls
            or total_tokens >= self.max_total_tokens
        )

    def stop_reason(self, iteration: int, tool_calls: int, total_tokens: int) -> str:
        if total_tokens >= self.max_total_tokens:
            return "token_budget_exhausted"
        if tool_calls >= self.max_tool_calls:
            return "tool_budget_exhausted"
        if iteration >= self.max_iterations:
            return "iteration_budget_exhausted"
        return "budget_exhausted"


class ScoutAgent(BaseAgent):
    name = "scout"

    def __init__(
        self,
        llm,
        tools: list[BaseTool],
        mode: ScoutMode = "legacy",
        max_iterations: int = 8,
        max_tool_calls: int = 12,
    ) -> None:
        super().__init__(llm, tools)
        self.mode = mode
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.last_run_stats: dict[str, Any] = {
            "mode": mode,
            "duration_ms": 0,
            "tool_call_count": 0,
            "iteration_count": 0,
            "submitted_deal_count": 0,
            "accepted_deal_count": 0,
            "rejected_deal_count": 0,
            "rejection_by_reason": {},
            "unique_destinations": [],
            "stop_reason": "not_started",
            "model": getattr(llm, "model", "unknown"),
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
        }

    async def discover(self, origin_city: str, days: int = 60, max_price: int = 1500) -> list[Deal]:
        if self.mode == "agentic":
            return await self._discover_agentic(origin_city, days, max_price)
        return await self._discover_legacy(origin_city, days, max_price)

    async def _discover_legacy(
        self,
        origin_city: str,
        days: int = 60,
        max_price: int = 1500,
    ) -> list[Deal]:
        del days
        started_at = perf_counter()
        search_tool = self.require_tool("web_search")
        fetch_tool = self.require_tool("web_fetch")
        parser_tool = self.require_tool("price_parser")
        source_note = self._source_note()

        destinations = await self._discover_destinations(search_tool, origin_city)
        logger.info("Scout destination candidates for %s: %s", origin_city, destinations)

        deals: list[Deal] = []
        for destination in destinations:
            context = await self._context_for_destination(
                search_tool=search_tool,
                fetch_tool=fetch_tool,
                origin_city=origin_city,
                destination=destination,
            )
            if not context:
                logger.info(
                    "Scout skipped destination=%s because no context was found",
                    destination,
                )
                continue

            parse_result = await parser_tool.execute(
                PriceParserInput(
                    text="\n\n".join(
                        [
                            f"Target destination: {destination}",
                            *context,
                            f"Source note: {source_note}",
                        ]
                    ),
                    origin_city=origin_city,
                    max_price_cny=max_price,
                )
            )
            if not parse_result.success:
                logger.warning(
                    "Scout price parsing failed for destination=%s: %s",
                    destination,
                    parse_result.error,
                )
                continue
            raw_deals = parse_result.data if isinstance(parse_result.data, list) else []
            destination_deals = self._validated_deals(raw_deals, destination, source_note)
            deals.extend(destination_deals[:2])

        self.last_run_stats = {
            "mode": "legacy",
            "duration_ms": int((perf_counter() - started_at) * 1000),
            "tool_call_count": 0,
            "iteration_count": 0,
            "submitted_deal_count": len(deals),
            "accepted_deal_count": len(deals),
            "rejected_deal_count": 0,
            "rejection_by_reason": {},
            "unique_destinations": sorted({deal.destination_city for deal in deals}),
            "stop_reason": "legacy_complete",
            "model": getattr(self.llm, "model", "unknown"),
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
        }
        return deals

    async def _discover_agentic(
        self,
        origin_city: str,
        days: int = 60,
        max_price: int = 1500,
    ) -> list[Deal]:
        started_at = perf_counter()
        budget = AgenticBudget(
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
        )
        messages: list[ChatMessage] = [
            {
                "role": "system",
                "content": self._build_agentic_system_prompt(origin_city, days, max_price),
            },
            {
                "role": "user",
                "content": (
                    f"Find low-price travel deals from {origin_city}. Budget: CNY {max_price}. "
                    "Submit each deal via submit_deal, then call finish."
                ),
            },
        ]
        tools_schema = self._build_agentic_tools_schema()
        submitted_deals: list[ExtractedDeal] = []
        context_fragments: list[str] = []
        tool_call_count = 0
        iteration_count = 0
        total_input_tokens = 0
        total_output_tokens = 0
        stop_reason = "budget_exhausted"

        while not budget.exhausted(
            iteration_count,
            tool_call_count,
            total_input_tokens + total_output_tokens,
        ):
            iteration_count += 1
            logger.info(
                "agentic scout iteration=%s tool_calls=%s city=%s",
                iteration_count,
                tool_call_count,
                origin_city,
            )
            response = await self.llm.chat_with_tools(messages, tools_schema)
            usage = response.get("usage") if isinstance(response, dict) else None
            if isinstance(usage, dict):
                total_input_tokens += int(usage.get("prompt_tokens", 0))
                total_output_tokens += int(usage.get("completion_tokens", 0))
            assistant_blocks = self._assistant_blocks(response)
            assistant_message = self._assistant_message_from_blocks(assistant_blocks)
            if assistant_message is not None:
                messages.append(assistant_message)

            tool_calls = [block for block in assistant_blocks if block.get("type") == "tool_call"]
            if not tool_calls:
                stop_reason = "no_tool_call"
                break

            stop_now = False
            for tool_call in tool_calls:
                if tool_call_count >= budget.max_tool_calls:
                    stop_reason = budget.stop_reason(
                        iteration_count,
                        tool_call_count,
                        total_input_tokens + total_output_tokens,
                    )
                    stop_now = True
                    break
                tool_call_count += 1
                name = self._tool_name(tool_call)
                args = self._tool_args(tool_call)

                if name == "finish":
                    stop_reason = str(args.get("reason", "finish"))
                    messages.append(self._tool_result_message(tool_call, {"ok": True}))
                    return self._finalize_agentic(
                        submitted=submitted_deals,
                        stop_reason=stop_reason,
                        origin_city=origin_city,
                        max_price=max_price,
                        full_context="\n\n".join(context_fragments),
                        duration_ms=int((perf_counter() - started_at) * 1000),
                        iteration_count=iteration_count,
                        tool_call_count=tool_call_count,
                        total_input_tokens=total_input_tokens,
                        total_output_tokens=total_output_tokens,
                    )

                if name == "submit_deal":
                    try:
                        extracted = self._args_to_extracted_deal(args, origin_city)
                    except Exception as exc:
                        messages.append(
                            self._tool_result_message(tool_call, {"ok": False, "error": str(exc)})
                        )
                    else:
                        submitted_deals.append(extracted)
                        messages.append(
                            self._tool_result_message(
                                tool_call,
                                {"ok": True, "accepted": True},
                            )
                        )
                    continue

                if name == "web_search":
                    result = await self.require_tool("web_search").execute(WebSearchInput(**args))
                    context_fragments.extend(self._context_chunks_from_search(result))
                    messages.append(
                        self._tool_result_message(tool_call, self._truncate_tool_result(result))
                    )
                    continue

                if name == "web_fetch":
                    result = await self.require_tool("web_fetch").execute(WebFetchInput(**args))
                    chunk = self._context_chunk_from_fetch(result)
                    if chunk:
                        context_fragments.append(chunk)
                    messages.append(
                        self._tool_result_message(tool_call, self._truncate_tool_result(result))
                    )
                    continue

                logger.info("agentic scout received unknown tool=%s", name)
                messages.append(
                    self._tool_result_message(
                        tool_call,
                        {"ok": False, "error": f"unknown tool {name}"},
                    )
                )

            if stop_now:
                break

        if stop_reason == "budget_exhausted":
            stop_reason = budget.stop_reason(
                iteration_count,
                tool_call_count,
                total_input_tokens + total_output_tokens,
            )
        return self._finalize_agentic(
            submitted=submitted_deals,
            stop_reason=stop_reason,
            origin_city=origin_city,
            max_price=max_price,
            full_context="\n\n".join(context_fragments),
            duration_ms=int((perf_counter() - started_at) * 1000),
            iteration_count=iteration_count,
            tool_call_count=tool_call_count,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
        )

    def _discover_queries(self, origin_city: str) -> list[str]:
        return [
            f"{origin_city} 五一 低价出行 旅游推荐",
            f"{origin_city} 周末 短途旅行 低价推荐",
            f"{origin_city} 出发 特价机票 2026年5月",
            f"{origin_city} 春秋航空 亚洲航空 特价 目的地",
        ]

    async def _discover_destinations(self, search_tool: BaseTool, origin_city: str) -> list[str]:
        scores = dict.fromkeys(DESTINATION_ALIASES, 0)
        for query in self._discover_queries(origin_city):
            logger.info("Scout discovering destinations query=%s", query)
            result = await search_tool.execute(WebSearchInput(query=query, max_results=8))
            for item in self._items_from_result(result):
                text = self._snippet_from_item(item)
                for destination, aliases in DESTINATION_ALIASES.items():
                    if any(alias.casefold() in text.casefold() for alias in aliases):
                        scores[destination] += 1

        discovered = [
            destination
            for destination, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
            if score > 0
        ]
        if discovered:
            return discovered[:6]
        return ["曼谷", "清迈", "东京", "大阪", "首尔", "三亚"]

    async def _context_for_destination(
        self,
        search_tool: BaseTool,
        fetch_tool: BaseTool,
        origin_city: str,
        destination: str,
    ) -> list[str]:
        snippets: list[str] = []
        urls: list[str] = []
        seen: set[str] = set()
        for query in self._destination_queries(origin_city, destination):
            logger.info("Scout searching destination=%s query=%s", destination, query)
            result = await search_tool.execute(WebSearchInput(query=query, max_results=8))
            for item in self._items_from_result(result):
                key = self._result_key(item)
                if key in seen:
                    continue
                seen.add(key)
                snippets.append(self._snippet_from_item(item))
                url = str(item.get("url", ""))
                if url.startswith(("http://", "https://")):
                    urls.append(url)

        for url in self._top_urls(urls, limit=2):
            logger.info("Scout fetching destination=%s URL=%s", destination, url)
            result = await fetch_tool.execute(WebFetchInput(url=url, max_chars=3000))
            if not result.success:
                logger.warning(
                    "Scout skipped failed destination=%s URL=%s error=%s",
                    destination,
                    url,
                    result.error,
                )
                continue
            if isinstance(result.data, dict):
                text = str(result.data.get("text", ""))
                if text:
                    snippets.append(f"Fetched page\n{url}\n{text}")
        return snippets

    def _validated_deals(
        self,
        raw_deals: list[object],
        destination: str,
        source_note: str,
    ) -> list[Deal]:
        deals: list[Deal] = []
        for item in raw_deals:
            if not isinstance(item, dict):
                continue
            deal = Deal.model_validate(item)
            if not self._matches_destination(deal.destination_city, destination):
                logger.info(
                    "Scout skipped parsed deal destination=%s for target=%s",
                    deal.destination_city,
                    destination,
                )
                continue
            notes = deal.notes or source_note
            if "Tavily" not in notes:
                notes = f"{notes}；{source_note}"
            deals.append(deal.model_copy(update={"notes": notes}))
        return sorted(deals, key=lambda deal: (deal.price_cny_fen, deal.departure_date))

    def _destination_queries(self, origin_city: str, destination: str) -> list[str]:
        aliases = list(DESTINATION_ALIASES.get(destination, {destination}))
        english_alias = next(
            (alias for alias in aliases if alias.isascii() and len(alias) > 3),
            destination,
        )
        return [
            f"{origin_city} 飞 {destination} 特价",
            f"{origin_city} 飞 {destination} 机票",
            f"{origin_city} {destination} 廉航 促销",
            f"{origin_city} 春秋航空 {destination} 特价",
            f"{origin_city} 亚洲航空 {destination} 促销",
            f"cheap flights from {origin_city} to {english_alias} May 2026",
        ]

    def _build_agentic_system_prompt(self, origin_city: str, days: int, max_price: int) -> str:
        return AGENTIC_SCOUT_SYSTEM_PROMPT.format(
            origin_city=origin_city,
            days=days,
            max_price=max_price,
            max_tool_calls=self.max_tool_calls,
        )

    def _build_agentic_tools_schema(self) -> list[ToolSchema]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": (
                        "Search the web for travel information. Returns up to N results "
                        "with title/url/snippet."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Chinese or English search query",
                            },
                            "max_results": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": (
                        "Fetch full text content from a URL. Use this when web_search snippets "
                        "are not enough."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "max_chars": {"type": "integer", "default": 3000},
                        },
                        "required": ["url"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_deal",
                    "description": (
                        "Submit a verified low-price travel deal. Each field must be traceable "
                        "to evidence from web_search or web_fetch results."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin_city": {"type": "string"},
                            "destination_city": {"type": "string"},
                            "price_cny": {"type": "integer", "minimum": 0},
                            "transport_mode": {
                                "enum": ["flight", "train", "bus", "carpool"]
                            },
                            "departure_date": {
                                "type": "string",
                                "description": "YYYY-MM-DD",
                            },
                            "return_date": {"type": ["string", "null"]},
                            "is_round_trip": {"type": "boolean"},
                            "operator": {"type": ["string", "null"]},
                            "booking_url": {"type": ["string", "null"]},
                            "source_url": {"type": ["string", "null"]},
                            "evidence_text": {
                                "type": "string",
                                "description": (
                                    "The EXACT substring from a search result or fetched page "
                                    "that contains the price and destination. Must be a contiguous "
                                    "quote, do not paraphrase."
                                ),
                            },
                        },
                        "required": [
                            "origin_city",
                            "destination_city",
                            "price_cny",
                            "transport_mode",
                            "departure_date",
                            "evidence_text",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "finish",
                    "description": (
                        "Stop the agentic loop. Call this when you have submitted enough "
                        "quality deals or determined no more good deals exist."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Why you are stopping",
                            }
                        },
                        "required": ["reason"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def _assistant_blocks(self, response: ToolCallResult) -> list[dict[str, Any]]:
        content = response.get("content")
        if isinstance(content, list):
            return [item for item in content if isinstance(item, dict)]
        blocks: list[dict[str, Any]] = []
        text = response.get("text") or response.get("content")
        if isinstance(text, str) and text:
            blocks.append({"type": "text", "text": text})
        tool_calls = response.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function", {})
                if not isinstance(function, dict):
                    continue
                arguments = function.get("arguments")
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        pass
                blocks.append(
                    {
                        "type": "tool_call",
                        "id": call.get("id"),
                        "name": function.get("name"),
                        "arguments": arguments if isinstance(arguments, dict) else {},
                    }
                )
        return blocks

    def _assistant_message_from_blocks(
        self,
        assistant_blocks: list[dict[str, Any]],
    ) -> ChatMessage | None:
        if not assistant_blocks:
            return None
        text_parts = [
            str(block.get("text", "")) for block in assistant_blocks if block.get("type") == "text"
        ]
        tool_calls: list[dict[str, Any]] = []
        for block in assistant_blocks:
            if block.get("type") != "tool_call":
                continue
            arguments = block.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        message: ChatMessage = {
            "role": "assistant",
            "content": "\n".join(part for part in text_parts if part),
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message

    def _tool_result_message(
        self,
        tool_call: dict[str, Any],
        payload: dict[str, Any],
    ) -> ChatMessage:
        return {
            "role": "tool",
            "tool_call_id": str(tool_call.get("id", "")),
            "content": json.dumps(payload, ensure_ascii=False),
        }

    def _tool_name(self, tool_call: dict[str, Any]) -> str:
        return str(tool_call.get("name", "")).strip()

    def _tool_args(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        arguments = tool_call.get("arguments", {})
        if isinstance(arguments, dict):
            return arguments
        return {}

    def _args_to_extracted_deal(self, args: dict[str, Any], origin_city: str) -> ExtractedDeal:
        payload = dict(args)
        payload.setdefault("origin_city", origin_city)
        payload.setdefault("return_date", None)
        payload.setdefault("is_round_trip", False)
        payload.setdefault("operator", None)
        payload.setdefault("booking_url", None)
        payload.setdefault("source_url", None)
        return ExtractedDeal.model_validate(payload)

    def _truncate_tool_result(self, result: ToolOutput) -> dict[str, Any]:
        if not result.success:
            return {"success": False, "error": result.error}
        if isinstance(result.data, list):
            trimmed: list[dict[str, Any]] = []
            for item in result.data[:5]:
                if not isinstance(item, dict):
                    continue
                trimmed.append(
                    {
                        "title": str(item.get("title", ""))[:200],
                        "url": str(item.get("url", "")),
                        "content": str(item.get("content", ""))[:300],
                    }
                )
            return {"success": True, "results": trimmed}
        if isinstance(result.data, dict):
            return {
                "success": True,
                "url": str(result.data.get("url", "")),
                "text": str(result.data.get("text", ""))[:1500],
            }
        if isinstance(result.data, str):
            return {"success": True, "text": result.data[:1500]}
        return {"success": True, "data": result.data}

    def _context_chunks_from_search(self, result: ToolOutput) -> list[str]:
        return [self._snippet_from_item(item) for item in self._items_from_result(result)]

    def _context_chunk_from_fetch(self, result: ToolOutput) -> str | None:
        if not result.success or not isinstance(result.data, dict):
            return None
        text = str(result.data.get("text", ""))
        url = str(result.data.get("url", ""))
        if not text:
            return None
        return f"Fetched page\n{url}\n{text}"

    def _finalize_agentic(
        self,
        *,
        submitted: list[ExtractedDeal],
        stop_reason: str,
        origin_city: str,
        max_price: int,
        full_context: str,
        duration_ms: int,
        iteration_count: int,
        tool_call_count: int,
        total_input_tokens: int,
        total_output_tokens: int,
    ) -> list[Deal]:
        validator = EvidenceValidator(DESTINATION_ALIASES)
        parser_tool = self.tools.get("price_parser")
        valid_deals: list[Deal] = []
        rejection_log: dict[str, int] = {}
        source_note = self._source_note()

        for extracted in submitted:
            result = validator.validate(extracted, full_context)
            if not result.is_valid:
                for reason in result.reasons:
                    rejection_log[reason.value] = rejection_log.get(reason.value, 0) + 1
                continue
            deal = self._extracted_to_deal(
                extracted=extracted,
                origin_city=origin_city,
                max_price=max_price,
                parser_tool=parser_tool,
                source_note=source_note,
            )
            if deal is None:
                continue
            valid_deals.append(deal)

        logger.info(
            "agentic scout finished",
            extra={
                "submitted_count": len(submitted),
                "accepted_count": len(valid_deals),
                "rejected_count": sum(rejection_log.values()),
                "rejection_by_reason": rejection_log,
                "stop_reason": stop_reason,
            },
        )
        self.last_run_stats = {
            "mode": "agentic",
            "duration_ms": duration_ms,
            "tool_call_count": tool_call_count,
            "iteration_count": iteration_count,
            "submitted_deal_count": len(submitted),
            "accepted_deal_count": len(valid_deals),
            "rejected_deal_count": sum(rejection_log.values()),
            "rejection_by_reason": rejection_log,
            "unique_destinations": sorted({deal.destination_city for deal in valid_deals}),
            "stop_reason": stop_reason,
            "model": getattr(self.llm, "model", "unknown"),
            "estimated_input_tokens": total_input_tokens,
            "estimated_output_tokens": total_output_tokens,
        }
        return valid_deals

    def _extracted_to_deal(
        self,
        *,
        extracted: ExtractedDeal,
        origin_city: str,
        max_price: int,
        parser_tool: BaseTool | None,
        source_note: str,
    ) -> Deal | None:
        if isinstance(parser_tool, PriceParserTool):
            deal = parser_tool._deal_from_extracted(extracted, origin_city, max_price)
        else:
            payload = {
                "source": "agentic",
                "origin_city": extracted.origin_city or origin_city,
                "origin_code": None,
                "destination_city": extracted.destination_city,
                "destination_code": None,
                "destination_country": None,
                "price_cny_fen": extracted.price_cny * 100,
                "transport_mode": extracted.transport_mode,
                "departure_date": extracted.departure_date,
                "return_date": extracted.return_date,
                "is_round_trip": extracted.is_round_trip,
                "operator": extracted.operator,
                "booking_url": extracted.booking_url or "https://example.com",
                "source_url": extracted.source_url,
                "notes": None,
            }
            try:
                deal = Deal.model_validate(payload)
            except Exception:
                logger.exception("agentic scout failed to convert extracted deal")
                return None
        if deal is None:
            return None
        notes = deal.notes or source_note
        if "Tavily" not in notes:
            notes = f"{notes}；{source_note}"
        return deal.model_copy(update={"notes": notes})

    def _items_from_result(self, result: ToolOutput) -> list[dict[str, object]]:
        if not result.success or not isinstance(result.data, list):
            return []
        return [item for item in result.data if isinstance(item, dict)]

    def _snippet_from_item(self, item: dict[str, object]) -> str:
        title = str(item.get("title", ""))
        url = str(item.get("url", ""))
        content = str(item.get("content", ""))
        return f"Search result\n{title}\n{url}\n{content}"

    def _result_key(self, item: dict[str, object]) -> str:
        url = str(item.get("url", "")).strip().casefold()
        if url:
            return url
        title = str(item.get("title", "")).strip().casefold()
        content = str(item.get("content", "")).strip().casefold()
        return f"{title}|{content[:160]}"

    def _top_urls(self, urls: list[str], limit: int) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            unique.append(url)
            if len(unique) >= limit:
                break
        return unique

    def _matches_destination(self, parsed_destination: str, target_destination: str) -> bool:
        parsed = parsed_destination.casefold()
        aliases = DESTINATION_ALIASES.get(target_destination, {target_destination})
        return any(alias.casefold() in parsed or parsed in alias.casefold() for alias in aliases)

    def _source_note(self) -> str:
        return (
            f"价格参考自 {date.today().isoformat()} Tavily 搜索结果，"
            "实际价格请以订票平台为准"
        )
