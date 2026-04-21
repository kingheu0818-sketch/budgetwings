"""One-off benchmark for price_parser.

Runs the current PriceParserTool against a fixed set of synthetic / recorded
Tavily-like inputs and reports parse-level metrics. This script is used
both BEFORE and AFTER the T2 refactor to produce before/after numbers.

Usage:
    python scripts/bench_price_parser.py --out data/bench/price_parser_<tag>.json

The tag is typically "baseline" before the refactor and "structured" after.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.orchestrator import build_llm  # noqa: E402
from config import Settings, get_settings  # noqa: E402
from llm.base import ChatMessage, LLMAdapter, LLMError, ToolCallResult, ToolSchema  # noqa: E402
from models.deal import Deal  # noqa: E402
from tools.price_parser import PriceParserInput, PriceParserTool  # noqa: E402

FIXTURE_PATH = Path("tests/fixtures/price_parser_samples.json")
DEALS_DIR = Path("data/deals")


class BenchmarkMockLLM(LLMAdapter):
    def __init__(self, sample: dict[str, Any]) -> None:
        super().__init__(model="bench-mock")
        self.sample = sample

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        del messages, tools
        return _baseline_response_for_sample(self.sample)

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        del messages, tools
        return {"provider": "mock", "tool_calls": []}

    async def extract_structured(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        del messages, schema, schema_name, schema_description
        return _structured_response_for_sample(self.sample)


async def main_async(args: argparse.Namespace) -> None:
    settings = get_settings()
    samples = load_samples()
    mock_mode = should_use_mock(settings)

    per_sample: list[dict[str, Any]] = []
    success_count = 0
    empty_result_count = 0
    error_count = 0
    total_deals_extracted = 0
    pydantic_validation_failures = 0

    shared_llm = None if mock_mode else build_llm(settings)

    for sample in samples:
        llm = BenchmarkMockLLM(sample) if mock_mode else shared_llm
        tool = PriceParserTool(llm)
        result = await tool.execute(
            PriceParserInput(text=sample["text"], origin_city=sample.get("origin_city"))
        )

        sample_errors: list[str] = []
        deal_count = 0
        if result.success:
            success_count += 1
            payload = result.data if isinstance(result.data, list) else []
            for item in payload:
                try:
                    Deal.model_validate(item)
                except Exception as exc:
                    pydantic_validation_failures += 1
                    sample_errors.append(f"Deal validation failed: {exc}")
                else:
                    deal_count += 1
            total_deals_extracted += deal_count
            if deal_count == 0:
                empty_result_count += 1
        else:
            error_count += 1
            if result.error:
                sample_errors.append(result.error)

        per_sample.append(
            {
                "sample_id": sample["sample_id"],
                "category": sample["category"],
                "success": result.success,
                "deal_count": deal_count,
                "errors": sample_errors,
            }
        )

    report = {
        "tag": args.tag,
        "timestamp": datetime.now(UTC).isoformat(),
        "provider": "mock" if mock_mode else settings.llm_provider,
        "model": "bench-mock" if mock_mode else settings.llm_model,
        "mock_mode": mock_mode,
        "total_samples": len(samples),
        "success_count": success_count,
        "empty_result_count": empty_result_count,
        "error_count": error_count,
        "total_deals_extracted": total_deals_extracted,
        "pydantic_validation_failures": pydantic_validation_failures,
        "per_sample": per_sample,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark BudgetWings price_parser")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    return parser


def should_use_mock(settings: Settings) -> bool:
    if os.getenv("BUDGETWINGS_BENCH_MOCK") == "1":
        return True
    if settings.llm_provider == "claude":
        return not bool(settings.anthropic_api_key)
    return not bool(settings.openai_api_key)


def load_samples() -> list[dict[str, Any]]:
    base_samples = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(base_samples, list):
        msg = "price parser fixture must be a list"
        raise ValueError(msg)
    samples = [dict(sample) for sample in base_samples if isinstance(sample, dict)]
    samples.extend(load_recorded_samples())
    return samples


def load_recorded_samples() -> list[dict[str, Any]]:
    deal_files = sorted(DEALS_DIR.glob("*.json"))
    if not deal_files:
        return []
    recorded_path = deal_files[-1]
    payload = json.loads(recorded_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []

    recorded: list[dict[str, Any]] = []
    for index, item in enumerate(payload[:3], start=1):
        if not isinstance(item, dict):
            continue
        origin = str(item.get("origin_city", "未知出发地"))
        destination = str(item.get("destination_city", "未知目的地"))
        price_fen = item.get("price_cny_fen", 0)
        price_yuan = int(price_fen) // 100 if isinstance(price_fen, int) else 0
        departure = str(item.get("departure_date", date.today().isoformat()))
        booking_url = str(item.get("booking_url", "https://example.com"))
        recorded.append(
            {
                "sample_id": f"recorded_{index}",
                "category": "recorded",
                "origin_city": origin,
                "behavior": "recorded_realistic",
                "text": (
                    f"Tavily snippet: {origin} -> {destination}，{departure} 单程 {price_yuan} 元。"
                    f" 平台链接：{booking_url}。页面还提到税费波动与舱位变化。"
                ),
            }
        )
    return recorded


def _baseline_response_for_sample(sample: dict[str, Any]) -> str:
    behavior = str(sample.get("behavior"))
    if behavior == "clean_json":
        return json.dumps({"deals": [_sample_deal(sample, 299, "flight")]}, ensure_ascii=False)
    if behavior == "clean_fenced_json":
        payload = json.dumps({"deals": [_sample_deal(sample, 488, "train")]}, ensure_ascii=False)
        return f"```json\n{payload}\n```"
    if behavior == "clean_list_json":
        payload = json.dumps([_sample_deal(sample, 199, "bus")], ensure_ascii=False)
        return payload
    if behavior == "noisy_two_blocks":
        good = json.dumps({"deals": [_sample_deal(sample, 520, "flight")]}, ensure_ascii=False)
        return (
            "先给你一个草稿：\n"
            "```json\n{\"summary\": \"候选很多\"}\n```\n"
            "真正结果在后面：\n"
            f"```json\n{good}\n```"
        )
    if behavior == "noisy_prefixed_text":
        good = json.dumps({"deals": [_sample_deal(sample, 520, "flight")]}, ensure_ascii=False)
        return f"以下是我提取的结果：\n{good}"
    if behavior == "noisy_valid_json":
        return json.dumps({"deals": [_sample_deal(sample, 680, "flight")]}, ensure_ascii=False)
    if behavior == "trap_past_date":
        return json.dumps(
            {
                "deals": [
                    _sample_deal(sample, 800, "flight", departure_date="2025-05-01", source="forum")
                ]
            },
            ensure_ascii=False,
        )
    if behavior == "trap_round_trip":
        return json.dumps(
            {
                "deals": [
                    _sample_deal(
                        sample,
                        699,
                        "flight",
                        is_round_trip=True,
                        return_date=(date.today() + timedelta(days=9)).isoformat(),
                    )
                ]
            },
            ensure_ascii=False,
        )
    if behavior == "trap_price_range":
        return json.dumps(
            {
                "deals": [
                    _sample_deal(sample, "399-699", "flight", booking_url="https://example.com")
                ]
            },
            ensure_ascii=False,
        )
    if behavior == "empty_no_json":
        return "这段文本没有明确票价，我无法提取结构化结果。"
    if behavior == "bad_invalid_json":
        return (
            "```json\n"
            "{\"deals\": [{\"origin_city\": \"杭州\" \"destination_city\": \"海口\"}]}\n"
            "```"
        )
    if behavior == "recorded_realistic":
        good = json.dumps(
            {"deals": [_sample_deal(sample, _recorded_price(sample), "flight")]},
            ensure_ascii=False,
        )
        if sample["sample_id"] == "recorded_2":
            return f"我先解释一下来源，再给结果：{good}"
        if sample["sample_id"] == "recorded_3":
            return (
                "```json\n{\"meta\": {\"confidence\": 0.42}}\n```\n"
                f"```json\n{good}\n```"
            )
        return f"```json\n{good}\n```"
    msg = f"Unhandled benchmark behavior: {behavior}"
    raise LLMError(msg)


def _structured_response_for_sample(sample: dict[str, Any]) -> dict[str, Any]:
    behavior = str(sample.get("behavior"))
    if behavior in {"clean_json", "clean_fenced_json", "clean_list_json"}:
        transport_map = {
            "clean_json": "flight",
            "clean_fenced_json": "train",
            "clean_list_json": "bus",
        }
        transport = transport_map[behavior]
        price = {"clean_json": 299, "clean_fenced_json": 488, "clean_list_json": 199}[behavior]
        return {"deals": [_structured_deal(sample, price, transport)]}
    if behavior == "noisy_two_blocks":
        return {"deals": [_structured_deal(sample, 520, "flight", operator="吉祥航空")]}
    if behavior == "noisy_prefixed_text":
        return {"deals": [_structured_deal(sample, 520, "flight", operator="春秋航空")]}
    if behavior == "noisy_valid_json":
        return {"deals": [_structured_deal(sample, 680, "flight", operator="亚洲航空")]}
    if behavior in {"trap_past_date", "trap_round_trip", "trap_price_range"}:
        return {"deals": []}
    if behavior in {"empty_no_json", "bad_invalid_json"}:
        return {"deals": []}
    if behavior == "recorded_realistic":
        return {"deals": [_structured_deal(sample, _recorded_price(sample), "flight")]}
    msg = f"Unhandled structured benchmark behavior: {behavior}"
    raise LLMError(msg)


def _sample_deal(
    sample: dict[str, Any],
    price_cny: int | str,
    transport_mode: str,
    *,
    departure_date: str | None = None,
    return_date: str | None = None,
    is_round_trip: bool = False,
    booking_url: str | None = None,
    source: str = "agent",
) -> dict[str, Any]:
    destination = _destination_for_sample(sample)
    return {
        "source": source,
        "origin_city": sample.get("origin_city", "深圳"),
        "destination_city": destination,
        "price_cny": price_cny,
        "transport_mode": transport_mode,
        "departure_date": departure_date or (date.today() + timedelta(days=21)).isoformat(),
        "return_date": return_date,
        "is_round_trip": is_round_trip,
        "booking_url": booking_url or f"https://example.com/{sample['sample_id']}",
        "source_url": f"https://source.example.com/{sample['sample_id']}",
    }


def _structured_deal(
    sample: dict[str, Any],
    price_cny: int,
    transport_mode: str,
    *,
    operator: str | None = None,
) -> dict[str, Any]:
    return {
        "origin_city": sample.get("origin_city", "深圳"),
        "destination_city": _destination_for_sample(sample),
        "price_cny": price_cny,
        "transport_mode": transport_mode,
        "departure_date": (date.today() + timedelta(days=21)).isoformat(),
        "return_date": None,
        "is_round_trip": False,
        "operator": operator,
        "booking_url": f"https://example.com/{sample['sample_id']}",
        "source_url": f"https://source.example.com/{sample['sample_id']}",
        "evidence_text": sample["text"][:120],
    }


def _destination_for_sample(sample: dict[str, Any]) -> str:
    sample_id = str(sample.get("sample_id", ""))
    mapping = {
        "clean_flight_shenzhen_bangkok": "曼谷",
        "clean_train_guangzhou_sanya": "三亚",
        "clean_bus_hangzhou_haikou": "海口",
        "noisy_multi_block_tokyo": "东京",
        "noisy_prefixed_commentary_osaka": "大阪",
        "noisy_long_snippet_chiangmai": "清迈",
        "trap_last_year_post": "曼谷",
        "trap_round_trip_price": "首尔",
        "trap_promo_range": "清迈",
        "empty_no_price": "未知目的地",
        "bad_unrelated_finance_news": "未知目的地",
        "bad_invalid_json_block": "海口",
        "recorded_1": "首尔",
        "recorded_2": "成都",
        "recorded_3": "曼谷",
    }
    return mapping.get(sample_id, "未知目的地")


def _recorded_price(sample: dict[str, Any]) -> int:
    text = str(sample.get("text", ""))
    digits = "".join(ch for ch in text if ch.isdigit() or ch == " ")
    parts = [part for part in digits.split() if part.isdigit()]
    if parts:
        return int(parts[-1])
    return 299


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
