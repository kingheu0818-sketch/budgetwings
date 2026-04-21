from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents.graph import build_graph_pipeline
from agents.orchestrator import build_orchestrator
from bot.data import load_latest_deals
from config import Settings, get_settings
from eval.dataset import filter_golden_deals, load_golden_deals
from eval.metrics import calculate_metrics
from models.deal import Deal
from models.persona import PersonaType

REPORTS_DIR = Path("eval/reports")


async def evaluate_pipeline(
    cities: list[str],
    persona_type: PersonaType,
    top_n: int = 10,
    engine: str = "graph",
    save: bool = False,
    settings: Settings | None = None,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    resolved = settings or get_settings()
    deals, source_mode = await _collect_eval_deals(
        cities=cities,
        persona_type=persona_type,
        top_n=top_n,
        engine=engine,
        settings=resolved,
    )
    golden_deals = filter_golden_deals(load_golden_deals(), cities)
    metrics = calculate_metrics(golden_deals, deals)
    report = {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "cities": cities,
            "persona": persona_type.value,
            "top_n": top_n,
            "engine": engine,
            "source_mode": source_mode,
            "openai_key_present": bool(resolved.openai_api_key or os.getenv("OPENAI_API_KEY")),
        },
        "counts": {
            "output_deals": len(deals),
            "golden_deals": len(golden_deals),
        },
        "metrics": metrics.as_dict(),
        "output_deals": [deal.model_dump(mode="json") for deal in deals],
    }
    markdown = render_report_markdown(report)
    report["markdown"] = markdown
    if save:
        _save_report(report, reports_dir)
    return report


def render_report_markdown(report: dict[str, Any]) -> str:
    metadata = report.get("metadata", {})
    counts = report.get("counts", {})
    metrics = report.get("metrics", {})
    lines = [
        "# BudgetWings Evaluation Report",
        "",
        f"- Generated at: {metadata.get('generated_at', 'unknown')}",
        f"- Cities: {', '.join(metadata.get('cities', []))}",
        f"- Persona: {metadata.get('persona', 'unknown')}",
        f"- Top N: {metadata.get('top_n', 0)}",
        f"- Engine: {metadata.get('engine', 'unknown')}",
        f"- Data source: {metadata.get('source_mode', 'unknown')}",
        "",
        "## Counts",
        "",
        f"- Output deals: {counts.get('output_deals', 0)}",
        f"- Golden deals: {counts.get('golden_deals', 0)}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for name in (
        "price_accuracy",
        "destination_recall",
        "destination_precision",
        "url_validity",
        "data_freshness",
        "diversity_score",
    ):
        lines.append(f"| {name} | {float(metrics.get(name, 0.0)):.4f} |")
    lines.extend(
        [
            "",
            "## Reading Guide",
            "",
            "- `price_accuracy`: agent prices inside the golden reasonable band "
            "(with ±30% tolerance).",
            "- `destination_recall`: how many golden destinations were found.",
            "- `destination_precision`: how many output destinations are expected "
            "by the golden set.",
            "- `url_validity`: share of deals with usable https booking URLs.",
            "- `data_freshness`: share of deals whose departure date is still in the future.",
            "- `diversity_score`: unique destinations divided by total deals.",
        ]
    )
    return "\n".join(lines)


async def _collect_eval_deals(
    cities: list[str],
    persona_type: PersonaType,
    top_n: int,
    engine: str,
    settings: Settings,
) -> tuple[list[Deal], str]:
    has_live_openai = settings.llm_provider == "openai" and (
        settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    )
    if has_live_openai:
        orchestrator = (
            build_orchestrator(settings) if engine == "legacy" else build_graph_pipeline(settings)
        )
        deals = await orchestrator.run_many(cities=cities, persona_type=persona_type, top_n=top_n)
        return deals, "live_pipeline"
    latest_deals = load_latest_deals()
    local_deals = [
        deal
        for deal in latest_deals
        if deal.origin_city.casefold() in {city.casefold() for city in cities}
    ]
    if local_deals:
        return local_deals[:top_n], "local_snapshot"
    if latest_deals:
        return latest_deals[:top_n], "local_snapshot_unfiltered"
    msg = (
        "No OPENAI_API_KEY found, and there are no local deals matching the requested city. "
        "Run the pipeline once or place sample deals under data/deals/."
    )
    raise RuntimeError(msg)


def _save_report(report: dict[str, Any], reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    generated_at = str(
        report.get("metadata", {}).get("generated_at", datetime.now(UTC).isoformat())
    )
    date_stamp = generated_at[:10]
    json_path = reports_dir / f"{date_stamp}.json"
    markdown_path = reports_dir / f"{date_stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(str(report.get("markdown", "")) + "\n", encoding="utf-8")
    return json_path, markdown_path
