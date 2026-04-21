from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.orchestrator import build_llm, build_scout_llm  # noqa: E402
from agents.scout import ScoutAgent  # noqa: E402
from config import Settings  # noqa: E402
from llm.base import ChatMessage, LLMAdapter, ToolCallResult, ToolSchema  # noqa: E402
from tools.base import BaseTool, ToolInput, ToolOutput  # noqa: E402
from tools.destinations import DESTINATION_ALIASES  # noqa: E402
from tools.price_parser import PriceParserTool  # noqa: E402
from tools.web_fetch import WebFetchTool  # noqa: E402
from tools.web_search import WebSearchTool  # noqa: E402

BENCH_JSON_PATH = Path("data/bench/scout_mode_comparison.json")
BENCH_MD_PATH = Path("data/bench/T4B_legacy_vs_agentic.md")


class LegacyBenchSearchTool(BaseTool):
    name = "web_search"
    description = "Deterministic search tool for legacy scout benchmark."

    async def execute(self, input: ToolInput) -> ToolOutput:
        query = getattr(input, "query", "")
        if "五一" in query or "周末" in query or "特价机票" in query:
            return ToolOutput(
                success=True,
                data=[
                    {
                        "title": "曼谷特价",
                        "url": "https://bench.example.com/bangkok",
                        "content": "深圳飞曼谷 2026-05-12 单程 399 元，春秋航空",
                    },
                    {
                        "title": "三亚特价",
                        "url": "https://bench.example.com/sanya",
                        "content": "深圳飞三亚 2026-05-18 单程 430 元，南方航空",
                    },
                ],
            )
        if "曼谷" in query:
            return ToolOutput(
                success=True,
                data=[
                    {
                        "title": "曼谷特价",
                        "url": "https://bench.example.com/bangkok",
                        "content": "深圳飞曼谷 2026-05-12 单程 399 元，春秋航空",
                    }
                ],
            )
        if "三亚" in query:
            return ToolOutput(
                success=True,
                data=[
                    {
                        "title": "三亚特价",
                        "url": "https://bench.example.com/sanya",
                        "content": "深圳飞三亚 2026-05-18 单程 430 元，南方航空",
                    }
                ],
            )
        return ToolOutput(success=True, data=[])


class BenchFetchTool(BaseTool):
    name = "web_fetch"
    description = "Deterministic fetch tool for benchmark runs."

    async def execute(self, input: ToolInput) -> ToolOutput:
        url = getattr(input, "url", "")
        mapping = {
            "https://bench.example.com/bangkok": (
                "页面详情：深圳飞曼谷 2026-05-12 单程 399 元，春秋航空。"
                "预订链接 https://bench.example.com/book/bangkok"
            ),
            "https://bench.example.com/sanya": (
                "页面详情：深圳飞三亚 2026-05-18 单程 430 元，南方航空。"
                "预订链接 https://bench.example.com/book/sanya"
            ),
            "https://bench.example.com/xian": (
                "页面详情：深圳飞西安 2026-05-21 单程 460 元，东方航空。"
                "预订链接 https://bench.example.com/book/xian"
            ),
            "https://bench.example.com/chongqing": (
                "页面详情：深圳飞重庆 2026-05-24 单程 380 元，重庆航空。"
                "预订链接 https://bench.example.com/book/chongqing"
            ),
        }
        return ToolOutput(success=True, data={"url": url, "text": mapping.get(url, "")})


class LegacyBenchParserTool(BaseTool):
    name = "price_parser"
    description = "Deterministic price parser for legacy scout benchmark."

    async def execute(self, input: ToolInput) -> ToolOutput:
        text = str(getattr(input, "text", ""))
        if "Target destination: 曼谷" in text:
            return ToolOutput(success=True, data=[self._deal("曼谷", 399, "2026-05-12")])
        if "Target destination: 三亚" in text:
            return ToolOutput(success=True, data=[self._deal("三亚", 430, "2026-05-18")])
        return ToolOutput(success=True, data=[])

    def _deal(self, destination: str, price_cny: int, departure_date: str) -> dict[str, Any]:
        booking_slug = {
            "曼谷": "bangkok",
            "三亚": "sanya",
        }[destination]
        return {
            "source": "agent",
            "origin_city": "深圳",
            "destination_city": destination,
            "price_cny_fen": price_cny * 100,
            "transport_mode": "flight",
            "departure_date": departure_date,
            "booking_url": f"https://bench.example.com/book/{booking_slug}",
            "source_url": f"https://bench.example.com/{booking_slug}",
            "notes": None,
        }


class ScriptedAgenticLLM(LLMAdapter):
    def __init__(self) -> None:
        super().__init__(model="bench-agentic")
        self.index = 0
        self.responses = self._build_responses()

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        del messages, tools
        return ""

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        del messages, tools
        if self.index >= len(self.responses):
            return {
                "provider": "fake",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "No more actions."}],
                "usage": {
                    "prompt_tokens": 150,
                    "completion_tokens": 30,
                    "total_tokens": 180,
                },
            }
        response = self.responses[self.index]
        self.index += 1
        return response

    async def extract_structured(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        return {"deals": []}

    def _build_responses(self) -> list[ToolCallResult]:
        return [
            self._response(
                "1",
                "web_search",
                {"query": "深圳 周末 低价旅行", "max_results": 5},
            ),
            self._response(
                "2",
                "submit_deal",
                {
                    "origin_city": "深圳",
                    "destination_city": "曼谷",
                    "price_cny": 399,
                    "transport_mode": "flight",
                    "departure_date": "2026-05-12",
                    "operator": "春秋航空",
                    "booking_url": "https://bench.example.com/book/bangkok",
                    "source_url": "https://bench.example.com/bangkok",
                    "evidence_text": "深圳飞曼谷 2026-05-12 单程 399 元，春秋航空",
                },
            ),
            self._response(
                "3",
                "web_search",
                {"query": "深圳 飞 西安 特价", "max_results": 5},
            ),
            self._response(
                "4",
                "submit_deal",
                {
                    "origin_city": "深圳",
                    "destination_city": "西安",
                    "price_cny": 460,
                    "transport_mode": "flight",
                    "departure_date": "2026-05-21",
                    "operator": "东方航空",
                    "booking_url": "https://bench.example.com/book/xian",
                    "source_url": "https://bench.example.com/xian",
                    "evidence_text": "深圳飞西安 2026-05-21 单程 460 元，东方航空",
                },
            ),
            self._response(
                "5",
                "web_search",
                {"query": "深圳 飞 重庆 特价", "max_results": 5},
            ),
            self._response(
                "6",
                "submit_deal",
                {
                    "origin_city": "深圳",
                    "destination_city": "重庆",
                    "price_cny": 380,
                    "transport_mode": "flight",
                    "departure_date": "2026-05-24",
                    "operator": "重庆航空",
                    "booking_url": "https://bench.example.com/book/chongqing",
                    "source_url": "https://bench.example.com/chongqing",
                    "evidence_text": "深圳飞重庆 2026-05-24 单程 380 元，重庆航空",
                },
            ),
            self._response(
                "7",
                "submit_deal",
                {
                    "origin_city": "深圳",
                    "destination_city": "首尔",
                    "price_cny": 799,
                    "transport_mode": "flight",
                    "departure_date": "2026-05-30",
                    "operator": "韩亚航空",
                    "booking_url": "https://bench.example.com/book/seoul",
                    "source_url": "https://bench.example.com/seoul",
                    "evidence_text": "深圳飞首尔 2026-05-30 单程 799 元，韩亚航空",
                },
            ),
            self._response(
                "8",
                "finish",
                {"reason": "submitted enough diverse deals"},
            ),
        ]

    def _response(self, call_id: str, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        return {
            "provider": "fake",
            "stop_reason": "tool_use",
            "content": [
                {"type": "tool_call", "id": call_id, "name": name, "arguments": arguments}
            ],
            "usage": {
                "prompt_tokens": 180,
                "completion_tokens": 40,
                "total_tokens": 220,
            },
        }


class AgenticBenchSearchTool(BaseTool):
    name = "web_search"
    description = "Deterministic search tool for agentic benchmark."

    async def execute(self, input: ToolInput) -> ToolOutput:
        query = str(getattr(input, "query", ""))
        mapping = {
            "深圳 周末 低价旅行": [
                {
                    "title": "曼谷特价",
                    "url": "https://bench.example.com/bangkok",
                    "content": "深圳飞曼谷 2026-05-12 单程 399 元，春秋航空",
                }
            ],
            "深圳 飞 西安 特价": [
                {
                    "title": "西安特价",
                    "url": "https://bench.example.com/xian",
                    "content": "深圳飞西安 2026-05-21 单程 460 元，东方航空",
                }
            ],
            "深圳 飞 重庆 特价": [
                {
                    "title": "重庆特价",
                    "url": "https://bench.example.com/chongqing",
                    "content": "深圳飞重庆 2026-05-24 单程 380 元，重庆航空",
                }
            ],
        }
        return ToolOutput(success=True, data=mapping.get(query, []))


async def run_benchmark(city: str, mock: bool) -> dict[str, Any]:
    if mock:
        legacy_scout = ScoutAgent(
            ScriptedAgenticLLM(),
            [LegacyBenchSearchTool(), BenchFetchTool(), LegacyBenchParserTool()],
            mode="legacy",
        )
        agentic_scout = ScoutAgent(
            ScriptedAgenticLLM(),
            [AgenticBenchSearchTool(), BenchFetchTool(), LegacyBenchParserTool()],
            mode="agentic",
            max_iterations=8,
            max_tool_calls=12,
        )
        real_api = False
    else:
        settings = Settings()
        llm = build_llm(settings)
        scout_llm = build_scout_llm(settings)
        legacy_scout = ScoutAgent(
            llm,
            [WebSearchTool(settings), WebFetchTool(settings), PriceParserTool(llm)],
            mode="legacy",
            max_iterations=settings.scout_max_iterations,
            max_tool_calls=settings.scout_max_tool_calls,
        )
        agentic_scout = ScoutAgent(
            scout_llm,
            [WebSearchTool(settings), WebFetchTool(settings), PriceParserTool(llm)],
            mode="agentic",
            max_iterations=settings.scout_max_iterations,
            max_tool_calls=settings.scout_max_tool_calls,
        )
        real_api = True

    legacy_deals = await legacy_scout.discover(city)
    agentic_deals = await agentic_scout.discover(city)

    return {
        "probed_at": datetime.now(UTC).isoformat(),
        "city": city,
        "real_api": real_api,
        "results": [
            summarize_run(city, "legacy", legacy_scout, legacy_deals),
            summarize_run(city, "agentic", agentic_scout, agentic_deals),
        ],
    }


def summarize_run(city: str, mode: str, scout: ScoutAgent, deals: list[Any]) -> dict[str, Any]:
    stats = dict(scout.last_run_stats)
    accepted_destinations = sorted({deal.destination_city for deal in deals})
    whitelist = set(DESTINATION_ALIASES)
    return {
        "city": city,
        "mode": mode,
        "duration_ms": stats.get("duration_ms", 0),
        "tool_call_count": stats.get("tool_call_count", 0),
        "iteration_count": stats.get("iteration_count", 0),
        "submitted_deal_count": stats.get("submitted_deal_count", 0),
        "accepted_deal_count": stats.get("accepted_deal_count", 0),
        "rejected_deal_count": stats.get("rejected_deal_count", 0),
        "rejection_by_reason": stats.get("rejection_by_reason", {}),
        "unique_destinations": accepted_destinations,
        "stop_reason": stats.get("stop_reason", "unknown"),
        "model": stats.get("model", "unknown"),
        "estimated_input_tokens": stats.get("estimated_input_tokens"),
        "estimated_output_tokens": stats.get("estimated_output_tokens"),
        "destinations_outside_legacy_whitelist": [
            destination for destination in accepted_destinations if destination not in whitelist
        ],
    }


def build_markdown(report: dict[str, Any]) -> str:
    legacy = report["results"][0]
    agentic = report["results"][1]
    legacy_outside = len(legacy["destinations_outside_legacy_whitelist"])
    agentic_outside = len(agentic["destinations_outside_legacy_whitelist"])
    legacy_rejection_rate = rate(legacy["rejected_deal_count"], legacy["submitted_deal_count"])
    agentic_rejection_rate = rate(agentic["rejected_deal_count"], agentic["submitted_deal_count"])
    mode_label = "mock mode, reproducible" if not report["real_api"] else "real API mode"

    summary_rows = [
        (
            "Deals submitted",
            legacy["submitted_deal_count"],
            agentic["submitted_deal_count"],
            agentic["submitted_deal_count"] - legacy["submitted_deal_count"],
        ),
        (
            "Deals accepted (post evidence validation)",
            legacy["accepted_deal_count"],
            agentic["accepted_deal_count"],
            agentic["accepted_deal_count"] - legacy["accepted_deal_count"],
        ),
        (
            "Unique destinations discovered",
            len(legacy["unique_destinations"]),
            len(agentic["unique_destinations"]),
            len(agentic["unique_destinations"]) - len(legacy["unique_destinations"]),
        ),
        (
            "Destinations outside legacy whitelist",
            legacy_outside,
            agentic_outside,
            agentic_outside - legacy_outside,
        ),
        (
            "Average tool calls per run",
            legacy["tool_call_count"],
            agentic["tool_call_count"],
            agentic["tool_call_count"] - legacy["tool_call_count"],
        ),
        (
            "Average duration (ms)",
            legacy["duration_ms"],
            agentic["duration_ms"],
            agentic["duration_ms"] - legacy["duration_ms"],
        ),
        (
            "Evidence rejection rate",
            f"{legacy_rejection_rate:.1f}%",
            f"{agentic_rejection_rate:.1f}%",
            f"{agentic_rejection_rate - legacy_rejection_rate:+.1f} pp",
        ),
    ]

    lines = [
        "# T4-B Before/After: Legacy Pipeline vs Agentic Loop",
        "",
        f"## Summary ({mode_label})",
        "",
        "| Metric | Legacy | Agentic | Delta |",
        "|---|---:|---:|---:|",
    ]
    for metric, legacy_value, agentic_value, delta in summary_rows:
        delta_text = f"{delta:+d}" if isinstance(delta, int) else str(delta)
        lines.append(f"| {metric} | {legacy_value} | {agentic_value} | {delta_text} |")

    lines.extend(
        [
            "",
            "## Design rationale",
            "",
            (
                "1. We keep legacy mode because it is still the cheapest and most "
                "predictable path for scheduled batch runs, cron jobs, and CI smoke "
                "checks. Agentic mode is powerful, but not every job should spend "
                "tool budget and latency on open-ended exploration."
            ),
            (
                "2. Agentic mode does something legacy cannot: it chooses its own "
                "next query and decides when to stop. In this mock benchmark it "
                "surfaces `西安`, which sits outside the hardcoded legacy shortlist "
                "for this run, and it also adds `重庆`, which legacy did not find."
            ),
            (
                "3. The tradeoff is cost and complexity. Agentic mode uses more "
                "tool calls, more iterations, and more accumulated context. That is "
                "acceptable for interactive exploration, but it should not replace "
                "legacy as the default deterministic path."
            ),
            "",
            "## When to use which",
            "",
            "- 定时批量任务 -> legacy (cheap, stable, predictable)",
            "- 用户主动查询 -> agentic (broader coverage, adaptive search strategy)",
            "- 新 origin_city 的初次探索 -> agentic (can adjust queries on the fly)",
            "- CI/CD 冒烟测试 -> legacy (must stay reproducible)",
            "",
            "## Known limitations",
            "",
            (
                "- The mock benchmark is scripted and deterministic. It proves "
                "control flow and validation behavior, not real-model variance."
            ),
            (
                "- A real agentic run can still hit iteration or tool-call ceilings "
                "before it finds enough diversity."
            ),
            (
                "- Because `EvidenceValidator` falls back to exact-string matching "
                "for unknown destinations, agentic mode can admit an "
                "evidence-grounded city outside the alias table today. That is a "
                "real current constraint, not something we should hand-wave away."
            ),
            (
                "- Real API runs will cost more than the mock numbers here suggest, "
                "which is one more reason legacy remains the default."
            ),
            "",
            "## Two lines of defense, still intact",
            "",
            (
                "- T2 (structured output): agentic `submit_deal` still goes through "
                "a strict tool schema, so arguments stay valid JSON."
            ),
            (
                "- T3 (evidence validation): every submitted agentic deal is still "
                "validated against accumulated search/fetch context before it "
                "becomes a `Deal`."
            ),
        ]
    )
    return "\n".join(lines)


def rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator / denominator) * 100


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark legacy vs agentic scout modes")
    parser.add_argument("--city", required=True)
    parser.add_argument("--mock", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = asyncio.run(run_benchmark(args.city, args.mock))
    BENCH_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    BENCH_JSON_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown = build_markdown(report)
    BENCH_MD_PATH.write_text(markdown + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
