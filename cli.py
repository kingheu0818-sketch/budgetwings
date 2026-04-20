from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from agents.orchestrator import build_orchestrator
from models.deal import Deal
from models.persona import PersonaType


async def run_command(args: argparse.Namespace) -> None:
    orchestrator = build_orchestrator()
    deals = await orchestrator.run(
        city=args.city,
        persona_type=PersonaType(args.persona),
        top_n=args.top,
    )
    print(f"Saved {len(deals)} deals under data/deals/")


async def guide_command(args: argparse.Namespace) -> None:
    deal = find_deal(args.deal_id)
    orchestrator = build_orchestrator()
    markdown = await orchestrator.guide.generate(deal, PersonaType(args.persona), days=args.days)
    output_dir = Path("data/guides")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{deal.id}.md"
    output_path.write_text(markdown + "\n", encoding="utf-8")
    print(f"Saved guide -> {output_path}")


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BudgetWings AI Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run scout -> analyst -> guide pipeline")
    run_parser.add_argument("--city", required=True)
    run_parser.add_argument(
        "--persona",
        choices=[item.value for item in PersonaType],
        default="worker",
    )
    run_parser.add_argument("--top", type=int, default=10)
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

    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(args.handler(args))


if __name__ == "__main__":
    main()
