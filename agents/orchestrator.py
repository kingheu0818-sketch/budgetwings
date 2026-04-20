from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from agents.analyst import AnalystAgent
from agents.guide import GuideAgent
from agents.scout import ScoutAgent
from config import Settings, get_settings
from llm.base import LLMAdapter
from llm.claude import ClaudeAdapter
from llm.openai_adapter import OpenAIAdapter
from models.deal import Deal
from models.persona import PersonaType
from observability.tracer import LLMTracer
from tools.price_parser import PriceParserTool
from tools.web_fetch import WebFetchTool
from tools.web_search import WebSearchTool


class Orchestrator:
    def __init__(self, scout: ScoutAgent, analyst: AnalystAgent, guide: GuideAgent) -> None:
        self.scout = scout
        self.analyst = analyst
        self.guide = guide

    async def run(
        self,
        city: str,
        persona_type: PersonaType | str,
        top_n: int = 10,
        output_root: Path = Path("data"),
    ) -> list[Deal]:
        return await self.run_many([city], persona_type, top_n=top_n, output_root=output_root)

    async def run_many(
        self,
        cities: list[str],
        persona_type: PersonaType | str,
        top_n: int = 10,
        output_root: Path = Path("data"),
    ) -> list[Deal]:
        persona = PersonaType(persona_type)
        raw_deals: list[Deal] = []
        for city in cities:
            raw_deals.extend(await self.scout.discover(city))
        top_deals = await self.analyst.analyze(raw_deals, persona, top_n=top_n)
        self._write_deals(top_deals, output_root / "deals")
        for deal in top_deals[: min(3, len(top_deals))]:
            guide_markdown = await self.guide.generate(deal, persona)
            self._write_guide(deal, guide_markdown, output_root / "guides")
        return top_deals

    def _write_deals(self, deals: list[Deal], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{datetime.now(UTC).date().isoformat()}.json"
        payload = [deal.model_dump(mode="json") for deal in deals]
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path

    def _write_guide(self, deal: Deal, markdown: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{deal.id}.md"
        output_path.write_text(markdown + "\n", encoding="utf-8")
        return output_path


def build_llm(settings: Settings | None = None, tracer: LLMTracer | None = None) -> LLMAdapter:
    resolved = settings or get_settings()
    if resolved.llm_provider == "claude":
        if not resolved.anthropic_api_key:
            msg = "ANTHROPIC_API_KEY is required for Claude provider"
            raise ValueError(msg)
        return ClaudeAdapter(
            api_key=resolved.anthropic_api_key,
            model=resolved.llm_model,
            timeout_seconds=resolved.llm_timeout_seconds,
            tracer=tracer,
        )
    if not resolved.openai_api_key:
        msg = "OPENAI_API_KEY is required for OpenAI provider"
        raise ValueError(msg)
    return OpenAIAdapter(
        api_key=resolved.openai_api_key,
        model=resolved.llm_model,
        timeout_seconds=resolved.llm_timeout_seconds,
        base_url=resolved.openai_base_url,
        tracer=tracer,
    )


def build_orchestrator(settings: Settings | None = None) -> Orchestrator:
    resolved = settings or get_settings()
    llm = build_llm(resolved)
    search = WebSearchTool(resolved)
    fetch = WebFetchTool(resolved)
    parser = PriceParserTool(llm)
    scout = ScoutAgent(llm, [search, fetch, parser])
    analyst = AnalystAgent(llm, [])
    guide = GuideAgent(llm, [search])
    return Orchestrator(scout=scout, analyst=analyst, guide=guide)


async def _main_async(args: argparse.Namespace) -> None:
    orchestrator = build_orchestrator()
    deals = await orchestrator.run(
        city=args.city,
        persona_type=PersonaType(args.persona),
        top_n=args.top,
    )
    print(f"Generated {len(deals)} ranked deals")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BudgetWings AI agent pipeline")
    parser.add_argument("--city", required=True)
    parser.add_argument("--persona", choices=[item.value for item in PersonaType], default="worker")
    parser.add_argument("--top", type=int, default=10)
    asyncio.run(_main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
