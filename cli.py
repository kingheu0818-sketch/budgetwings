from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from agents.graph import build_graph_pipeline
from agents.orchestrator import build_orchestrator
from config import Settings
from eval.compare import compare_reports, load_report, render_comparison_markdown
from eval.runner import evaluate_pipeline
from models.deal import Deal
from models.persona import PersonaType


async def run_command(args: argparse.Namespace) -> None:
    settings = Settings()
    if args.scout_mode is not None:
        settings = settings.model_copy(update={"scout_mode": args.scout_mode})
    orchestrator = (
        build_orchestrator(settings) if args.engine == "legacy" else build_graph_pipeline(settings)
    )
    cities = parse_cities(args.city)
    deals = await orchestrator.run_many(
        cities=cities,
        persona_type=PersonaType(args.persona),
        top_n=args.top,
    )
    print(f"Saved {len(deals)} deals for {', '.join(cities)} under data/deals/")


async def guide_command(args: argparse.Namespace) -> None:
    deal = find_deal(args.deal_id)
    orchestrator = build_orchestrator()
    markdown = await orchestrator.guide.generate(deal, PersonaType(args.persona), days=args.days)
    output_dir = Path("data/guides")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{deal.id}.md"
    output_path.write_text(markdown + "\n", encoding="utf-8")
    print(f"Saved guide -> {output_path}")


async def eval_command(args: argparse.Namespace) -> None:
    report = await evaluate_pipeline(
        cities=parse_cities(args.city),
        persona_type=PersonaType(args.persona),
        top_n=args.top,
        engine=args.engine,
        save=args.save,
    )
    print(report["markdown"])


def eval_compare_command(args: argparse.Namespace) -> None:
    report1 = load_report(Path(args.report1))
    report2 = load_report(Path(args.report2))
    diff = compare_reports(report1, report2)
    print(render_comparison_markdown(diff))


def find_deal(deal_id: str, deals_dir: Path = Path("data/deals")) -> Deal:
    for path in sorted(deals_dir.glob("*.json"), reverse=True):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            continue
        for item in payload:
            if isinstance(item, dict) and item.get("id") == deal_id:
                return Deal.model_validate(item)
    msg = f"deal not found: {deal_id}"
    raise ValueError(msg)


def parse_cities(value: str) -> list[str]:
    cities = [city.strip() for city in value.split(",") if city.strip()]
    if not cities:
        msg = "--city must include at least one city"
        raise ValueError(msg)
    return cities


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BudgetWings AI Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run scout -> analyst -> guide pipeline")
    run_parser.add_argument(
        "--city",
        required=True,
        help="Origin city, or multiple cities separated by commas, e.g. 深圳,上海,北京",
    )
    run_parser.add_argument(
        "--persona",
        choices=[item.value for item in PersonaType],
        default="worker",
    )
    run_parser.add_argument("--top", type=int, default=10)
    run_parser.add_argument(
        "--engine",
        choices=["graph", "legacy"],
        default="graph",
        help="Pipeline engine to use. Defaults to graph.",
    )
    run_parser.add_argument(
        "--scout-mode",
        choices=["legacy", "agentic"],
        default=None,
        help="Override scout mode for this run.",
    )
    run_parser.set_defaults(handler=run_command)

    guide_parser = subparsers.add_parser("guide", help="Generate a guide for an existing deal")
    guide_parser.add_argument("--deal-id", required=True)
    guide_parser.add_argument(
        "--persona",
        choices=[item.value for item in PersonaType],
        default="worker",
    )
    guide_parser.add_argument("--days", type=int, default=2)
    guide_parser.set_defaults(handler=guide_command)

    eval_parser = subparsers.add_parser("eval", help="Evaluate pipeline output quality")
    eval_parser.add_argument("--city", required=True, help="One or more cities separated by commas")
    eval_parser.add_argument(
        "--persona",
        choices=[item.value for item in PersonaType],
        default="worker",
    )
    eval_parser.add_argument("--top", type=int, default=10)
    eval_parser.add_argument(
        "--engine",
        choices=["graph", "legacy"],
        default="graph",
        help="Pipeline engine to use when live evaluation is enabled.",
    )
    eval_parser.add_argument("--save", action="store_true", help="Save JSON and Markdown reports")
    eval_parser.set_defaults(handler=eval_command)

    compare_parser = subparsers.add_parser("eval-compare", help="Compare two evaluation reports")
    compare_parser.add_argument("--report1", required=True)
    compare_parser.add_argument("--report2", required=True)
    compare_parser.set_defaults(handler=eval_compare_command)

    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = build_parser().parse_args()
    result = args.handler(args)
    if asyncio.iscoroutine(result):
        asyncio.run(result)


if __name__ == "__main__":
    main()
