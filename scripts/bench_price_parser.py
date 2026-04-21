"""One-off benchmark for price_parser.

Runs the current PriceParserTool against a fixed set of synthetic / recorded
Tavily-like inputs and reports parse-level metrics. This script is used
both BEFORE and AFTER parser refactors to produce before/after numbers.

Usage:
    python scripts/bench_price_parser.py --out data/bench/price_parser_<tag>.json

Supported tags:
    - baseline
    - structured
    - structured_no_validation
    - structured_with_validation
    - smoke
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
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
from tools.evidence_validator import EvidenceValidator, ValidationResult  # noqa: E402
from tools.price_parser import PriceParserInput, PriceParserTool  # noqa: E402

FIXTURE_PATH = Path("tests/fixtures/price_parser_samples.json")
DEALS_DIR = Path("data/deals")
HALLUCINATION_SAMPLE_IDS = {
    "hallucinated_price",
    "hallucinated_destination",
    "hallucinated_evidence",
    "missing_evidence",
    "valid_evidence_control",
}
ACCEPT_CONTROL_CATEGORIES = {"clean", "noise", "recorded"}
ACCEPT_CONTROL_SAMPLE_IDS = {"valid_evidence_control"}


class AllowAllEvidenceValidator(EvidenceValidator):
    def __init__(self) -> None:
        super().__init__({})

    def validate(self, extracted: Any, source_text: str) -> ValidationResult:
        evidence_text = getattr(extracted, "evidence_text", "") or ""
        return ValidationResult(
            is_valid=True,
            reasons=(),
            evidence_text=self._normalize(evidence_text),
        )


class BenchmarkMockLLM(LLMAdapter):
    def __init__(self, sample: dict[str, Any], tag: str) -> None:
        super().__init__(model="bench-mock")
        self.sample = sample
        self.tag = tag

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        del messages, tools
        raise LLMError("chat() is not used in the structured benchmark harness")

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
        return _structured_response_for_sample(self.sample, self.tag)


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
    hallucination_injected_count = 0
    hallucination_rejected_count = 0
    false_positive_rejections = 0
    rejection_by_reason: dict[str, int] = {}

    shared_llm = None if mock_mode else build_llm(settings)
    validation_enabled = args.tag in {"structured_with_validation", "smoke"}

    for sample in samples:
        llm = BenchmarkMockLLM(sample, args.tag) if mock_mode else shared_llm
        validator = None if validation_enabled else AllowAllEvidenceValidator()
        tool = PriceParserTool(llm, evidence_validator=validator)
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
                except Exception as exc:  # pragma: no cover - metrics path
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

        for reason, count in tool.last_rejection_log.items():
            rejection_by_reason[reason] = rejection_by_reason.get(reason, 0) + count

        if sample["sample_id"] in HALLUCINATION_SAMPLE_IDS:
            hallucination_injected_count += 1
            expected_reason = sample.get("expected_rejection_reason")
            if expected_reason is not None and expected_reason in tool.last_rejection_log:
                hallucination_rejected_count += 1

        if (
            sample["category"] in ACCEPT_CONTROL_CATEGORIES
            or sample["sample_id"] in ACCEPT_CONTROL_SAMPLE_IDS
        ) and tool.last_rejected_count > 0:
            false_positive_rejections += tool.last_rejected_count

        per_sample.append(
            {
                "sample_id": sample["sample_id"],
                "category": sample["category"],
                "success": result.success,
                "deal_count": deal_count,
                "errors": sample_errors,
                "rejected_count": tool.last_rejected_count,
                "rejection_by_reason": dict(tool.last_rejection_log),
            }
        )

    hallucination_rejection_rate = (
        hallucination_rejected_count / hallucination_injected_count
        if hallucination_injected_count
        else 0.0
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
        "hallucination_injected_count": hallucination_injected_count,
        "hallucination_rejected_count": hallucination_rejected_count,
        "hallucination_rejection_rate": round(hallucination_rejection_rate, 4),
        "rejection_by_reason": rejection_by_reason,
        "false_positive_rejections": false_positive_rejections,
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
                "destination_city": destination,
                "behavior": "recorded_realistic",
                "text": (
                    f"Tavily snippet: {origin} -> {destination}，{departure} 单程 {price_yuan} 元。"
                    f" 平台链接：{booking_url}。页面还提到税费波动与舱位变化。"
                ),
            }
        )
    return recorded


def _structured_response_for_sample(sample: dict[str, Any], tag: str) -> dict[str, Any]:
    del tag
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
        return {"deals": [_structured_deal(sample, 699, "flight", operator="吉祥航空")]}
    if behavior == "noisy_prefixed_text":
        return {"deals": [_structured_deal(sample, 520, "flight", operator="春秋航空")]}
    if behavior == "noisy_valid_json":
        return {"deals": [_structured_deal(sample, 680, "flight", operator="亚洲航空")]}
    if behavior in {"trap_past_date", "trap_round_trip", "trap_price_range"}:
        return {"deals": []}
    if behavior in {"empty_no_json", "bad_invalid_json"}:
        return {"deals": []}
    if behavior == "hallucinated_price":
        return {
            "deals": [
                _structured_deal(
                    sample,
                    600,
                    "flight",
                    operator="泰国狮航",
                    evidence_text="深圳飞曼谷 2026-05-22 单程 CNY 1200，泰国狮航",
                )
            ]
        }
    if behavior == "hallucinated_destination":
        return {
            "deals": [
                _structured_deal(
                    sample,
                    880,
                    "flight",
                    destination_city="清迈",
                    operator="亚洲航空",
                    evidence_text="深圳飞曼谷 2026-05-23 单程 880 元，亚洲航空",
                )
            ]
        }
    if behavior == "hallucinated_evidence":
        return {
            "deals": [
                _structured_deal(
                    sample,
                    999,
                    "flight",
                    operator="大韩航空",
                    evidence_text="广州飞首尔 2026-05-25 只要 699 元，大韩航空秒杀",
                )
            ]
        }
    if behavior == "missing_evidence":
        return {
            "deals": [
                _structured_deal(
                    sample,
                    760,
                    "flight",
                    operator="春秋航空",
                    evidence_text="",
                )
            ]
        }
    if behavior == "valid_evidence_control":
        return {"deals": [_structured_deal(sample, 430, "flight", operator="四川航空")]}
    if behavior == "recorded_realistic":
        return {"deals": [_structured_deal(sample, _recorded_price(sample), "flight")]}
    msg = f"Unhandled structured benchmark behavior: {behavior}"
    raise LLMError(msg)


def _structured_deal(
    sample: dict[str, Any],
    price_cny: int,
    transport_mode: str,
    *,
    destination_city: str | None = None,
    operator: str | None = None,
    evidence_text: str | None = None,
) -> dict[str, Any]:
    return {
        "origin_city": sample.get("origin_city", "深圳"),
        "destination_city": destination_city or _destination_for_sample(sample),
        "price_cny": price_cny,
        "transport_mode": transport_mode,
        "departure_date": (date.today() + timedelta(days=21)).isoformat(),
        "return_date": None,
        "is_round_trip": False,
        "operator": operator,
        "booking_url": f"https://example.com/{sample['sample_id']}",
        "source_url": f"https://source.example.com/{sample['sample_id']}",
        "evidence_text": (
            _default_evidence_text(sample) if evidence_text is None else evidence_text
        ),
    }


def _default_evidence_text(sample: dict[str, Any]) -> str:
    text = str(sample["text"])
    return text[:120]


def _destination_for_sample(sample: dict[str, Any]) -> str:
    destination = sample.get("destination_city")
    if isinstance(destination, str) and destination.strip():
        return destination
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
        "hallucinated_price": "曼谷",
        "hallucinated_destination": "曼谷",
        "hallucinated_evidence": "首尔",
        "missing_evidence": "大阪",
        "valid_evidence_control": "三亚",
        "recorded_1": "首尔",
        "recorded_2": "成都",
        "recorded_3": "曼谷",
    }
    return mapping.get(sample_id, "未知目的地")


def _recorded_price(sample: dict[str, Any]) -> int:
    text = str(sample.get("text", ""))
    match = re.search(r"单程\s+(\d+)\s+元", text)
    if match:
        return int(match.group(1))
    fallback_match = re.search(r"(\d{2,4})\s+元", text)
    if fallback_match:
        return int(fallback_match.group(1))
    parts = re.findall(r"\d{2,4}", text)
    if parts:
        return int(parts[0])
    return 299


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
