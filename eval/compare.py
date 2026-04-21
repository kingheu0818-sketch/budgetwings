from __future__ import annotations

import json
from pathlib import Path
from typing import Any

METRIC_NAMES = (
    "price_accuracy",
    "destination_recall",
    "destination_precision",
    "url_validity",
    "data_freshness",
    "diversity_score",
)


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Evaluation report must be a JSON object: {path}"
        raise ValueError(msg)
    return payload


def compare_reports(report1: dict[str, Any], report2: dict[str, Any]) -> dict[str, Any]:
    metrics1 = _extract_metrics(report1)
    metrics2 = _extract_metrics(report2)
    comparison: dict[str, dict[str, float | str]] = {}
    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []

    for name in METRIC_NAMES:
        before = metrics1.get(name, 0.0)
        after = metrics2.get(name, 0.0)
        delta = round(after - before, 4)
        status = "unchanged"
        if delta > 0:
            status = "improved"
            improved.append(name)
        elif delta < 0:
            status = "regressed"
            regressed.append(name)
        else:
            unchanged.append(name)
        comparison[name] = {
            "before": before,
            "after": after,
            "delta": delta,
            "status": status,
        }

    return {
        "report_1": _report_label(report1),
        "report_2": _report_label(report2),
        "metrics": comparison,
        "improved": improved,
        "regressed": regressed,
        "unchanged": unchanged,
    }


def render_comparison_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Comparison",
        "",
        f"- Baseline: {diff['report_1']}",
        f"- Candidate: {diff['report_2']}",
        "",
        "## Summary",
        "",
        f"- Improved: {', '.join(diff['improved']) or 'None'}",
        f"- Regressed: {', '.join(diff['regressed']) or 'None'}",
        f"- Unchanged: {', '.join(diff['unchanged']) or 'None'}",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Before | After | Delta | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, values in diff["metrics"].items():
        lines.append(
            "| "
            f"{name} | {values['before']:.4f} | {values['after']:.4f} | "
            f"{values['delta']:+.4f} | {values['status']} |"
        )
    return "\n".join(lines)


def _extract_metrics(report: dict[str, Any]) -> dict[str, float]:
    raw_metrics = report.get("metrics", {})
    if not isinstance(raw_metrics, dict):
        return {}
    metrics: dict[str, float] = {}
    for name in METRIC_NAMES:
        value = raw_metrics.get(name, 0.0)
        metrics[name] = float(value)
    return metrics


def _report_label(report: dict[str, Any]) -> str:
    metadata = report.get("metadata", {})
    if isinstance(metadata, dict) and "generated_at" in metadata:
        return str(metadata["generated_at"])
    return "unknown"
