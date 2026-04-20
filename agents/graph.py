from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.analyst import AnalystAgent
from agents.guide import GuideAgent
from agents.orchestrator import build_llm
from agents.scout import ScoutAgent
from agents.validator import validate_deals
from config import Settings, get_settings
from models.deal import Deal
from models.persona import PersonaType
from tools.price_parser import PriceParserTool
from tools.web_fetch import WebFetchTool
from tools.web_search import WebSearchTool

logger = logging.getLogger(__name__)


class PipelineState(TypedDict):
    city: str
    persona: PersonaType
    top_n: int
    raw_deals: list[Deal]
    validated_deals: list[Deal]
    ranked_deals: list[Deal]
    guides: dict[str, str]
    errors: list[str]
    retry_count: int


class ScoutLike(Protocol):
    async def discover(self, origin_city: str, days: int = 60, max_price: int = 1500) -> list[Deal]:
        ...


class AnalystLike(Protocol):
    async def analyze(
        self,
        deals: Sequence[Deal],
        persona_type: PersonaType,
        top_n: int = 10,
    ) -> list[Deal]:
        ...


class GuideLike(Protocol):
    async def generate(self, deal: Deal, persona_type: PersonaType, days: int = 2) -> str:
        ...


class GraphPipeline:
    node_names = {
        "scout_node",
        "validate_node",
        "analyst_node",
        "guide_node",
        "save_node",
        "retry_node",
    }

    def __init__(
        self,
        scout: ScoutLike,
        analyst: AnalystLike,
        guide: GuideLike,
        output_root: Path = Path("data"),
    ) -> None:
        self.scout = scout
        self.analyst = analyst
        self.guide = guide
        self.output_root = output_root
        self.app: Any = self._build_graph().compile()

    async def run(
        self,
        city: str,
        persona_type: PersonaType | str,
        top_n: int = 10,
        output_root: Path | None = None,
    ) -> list[Deal]:
        original_output_root = self.output_root
        if output_root is not None:
            self.output_root = output_root
        try:
            result = await self.app.ainvoke(self._initial_state(city, persona_type, top_n))
        finally:
            self.output_root = original_output_root
        ranked = result.get("ranked_deals", [])
        return list(ranked) if isinstance(ranked, list) else []

    async def run_many(
        self,
        cities: list[str],
        persona_type: PersonaType | str,
        top_n: int = 10,
        output_root: Path | None = None,
    ) -> list[Deal]:
        all_deals: list[Deal] = []
        for city in cities:
            all_deals.extend(
                await self.run(
                    city=city,
                    persona_type=persona_type,
                    top_n=top_n,
                    output_root=output_root,
                )
            )
        if len(cities) > 1:
            output_base = output_root or self.output_root
            ranked = await self.analyst.analyze(all_deals, PersonaType(persona_type), top_n=top_n)
            self._write_deals(ranked, output_base / "deals")
            return ranked
        return all_deals

    async def scout_node(self, state: PipelineState) -> dict[str, list[Deal] | list[str]]:
        retry_count = state["retry_count"]
        days = 90 if retry_count > 0 else 60
        max_price = 2000 if retry_count > 0 else 1500
        try:
            raw_deals = await self.scout.discover(
                state["city"],
                days=days,
                max_price=max_price,
            )
        except Exception as exc:
            logger.exception("Scout node failed")
            return {
                "raw_deals": [],
                "errors": [*state["errors"], f"scout_node failed: {exc}"],
            }
        return {"raw_deals": raw_deals}

    async def validate_node(self, state: PipelineState) -> dict[str, list[Deal] | list[str]]:
        result = validate_deals(state["raw_deals"])
        return {
            "validated_deals": result.valid_deals,
            "errors": [*state["errors"], *result.errors],
        }

    async def analyst_node(self, state: PipelineState) -> dict[str, list[Deal] | list[str]]:
        try:
            ranked = await self.analyst.analyze(
                state["validated_deals"],
                state["persona"],
                top_n=state["top_n"],
            )
        except Exception as exc:
            logger.exception("Analyst node failed")
            return {
                "ranked_deals": [],
                "errors": [*state["errors"], f"analyst_node failed: {exc}"],
            }
        return {"ranked_deals": ranked}

    async def guide_node(self, state: PipelineState) -> dict[str, dict[str, str] | list[str]]:
        guides: dict[str, str] = {}
        errors = list(state["errors"])
        for deal in state["ranked_deals"][:3]:
            try:
                guides[deal.id] = await self.guide.generate(deal, state["persona"])
            except Exception as exc:
                logger.exception("Guide node failed for deal id=%s", deal.id)
                errors.append(f"guide_node failed for {deal.id}: {exc}")
        return {"guides": guides, "errors": errors}

    async def save_node(self, state: PipelineState) -> dict[str, list[str]]:
        self._write_deals(state["ranked_deals"], self.output_root / "deals")
        self._write_guides(state["guides"], self.output_root / "guides")
        if not state["raw_deals"]:
            return {"errors": [*state["errors"], "no raw deals found after retry"]}
        if state["raw_deals"] and not state["validated_deals"]:
            return {"errors": [*state["errors"], "no valid deals found after retry"]}
        return {}

    async def retry_node(
        self,
        state: PipelineState,
    ) -> dict[str, int | list[Deal] | list[str] | dict[str, str]]:
        next_count = state["retry_count"] + 1
        message = (
            f"retry_node expanding search for {state['city']} "
            f"(attempt {next_count} of 1)"
        )
        logger.info(message)
        return {
            "retry_count": next_count,
            "raw_deals": [],
            "validated_deals": [],
            "ranked_deals": [],
            "guides": {},
            "errors": [*state["errors"], message],
        }

    def graph_nodes(self) -> set[str]:
        return set(self.node_names)

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(PipelineState)
        graph.add_node("scout_node", self.scout_node)
        graph.add_node("validate_node", self.validate_node)
        graph.add_node("analyst_node", self.analyst_node)
        graph.add_node("guide_node", self.guide_node)
        graph.add_node("save_node", self.save_node)
        graph.add_node("retry_node", self.retry_node)

        graph.add_edge(START, "scout_node")
        graph.add_conditional_edges(
            "scout_node",
            self._after_scout,
            {
                "validate_node": "validate_node",
                "retry_node": "retry_node",
                "save_node": "save_node",
            },
        )
        graph.add_conditional_edges(
            "validate_node",
            self._after_validate,
            {
                "analyst_node": "analyst_node",
                "retry_node": "retry_node",
                "save_node": "save_node",
            },
        )
        graph.add_edge("retry_node", "scout_node")
        graph.add_edge("analyst_node", "guide_node")
        graph.add_edge("guide_node", "save_node")
        graph.add_edge("save_node", END)
        return graph

    def _after_scout(self, state: PipelineState) -> str:
        if state["raw_deals"]:
            return "validate_node"
        if state["retry_count"] < 1:
            return "retry_node"
        return "save_node"

    def _after_validate(self, state: PipelineState) -> str:
        if state["validated_deals"]:
            return "analyst_node"
        if state["retry_count"] < 1:
            return "retry_node"
        return "save_node"

    def _initial_state(
        self,
        city: str,
        persona_type: PersonaType | str,
        top_n: int,
    ) -> PipelineState:
        return {
            "city": city,
            "persona": PersonaType(persona_type),
            "top_n": top_n,
            "raw_deals": [],
            "validated_deals": [],
            "ranked_deals": [],
            "guides": {},
            "errors": [],
            "retry_count": 0,
        }

    def _write_deals(self, deals: list[Deal], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{datetime.now(UTC).date().isoformat()}.json"
        output_path.write_text(
            json.dumps(
                [deal.model_dump(mode="json") for deal in deals],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return output_path

    def _write_guides(self, guides: dict[str, str], output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for deal_id, markdown in guides.items():
            output_path = output_dir / f"{deal_id}.md"
            output_path.write_text(markdown + "\n", encoding="utf-8")
            paths.append(output_path)
        return paths


def build_graph_pipeline(settings: Settings | None = None) -> GraphPipeline:
    resolved = settings or get_settings()
    llm = build_llm(resolved)
    search = WebSearchTool(resolved)
    fetch = WebFetchTool(resolved)
    parser = PriceParserTool(llm)
    scout = ScoutAgent(llm, [search, fetch, parser])
    analyst = AnalystAgent(llm, [])
    guide = GuideAgent(llm, [search])
    return GraphPipeline(scout=scout, analyst=analyst, guide=guide)
