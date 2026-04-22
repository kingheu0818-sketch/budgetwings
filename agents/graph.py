from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.analyst import AnalystAgent
from agents.guide import GuideAgent
from agents.orchestrator import build_llm, build_scout_llm
from agents.scout import ScoutAgent
from agents.validator import validate_deals
from config import Settings, get_settings
from db.models import SearchLog
from db.repository import build_deals_snapshot_path, save_deals, save_search_log
from models.deal import Deal
from models.persona import PersonaType
from observability.tracer import LLMTracer
from rag.knowledge_base import KnowledgeBase
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
    knowledge_context: dict[str, str]
    guides: dict[str, str]
    errors: list[str]
    retry_count: int
    trace_id: str | None


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
    async def generate(
        self,
        deal: Deal,
        persona_type: PersonaType,
        days: int = 2,
        knowledge_context: str | None = None,
    ) -> str:
        ...


class KnowledgeLike(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[str]:
        ...

    def add_deal_history(self, deal: Deal) -> None:
        ...


class GraphPipeline:
    node_names = {
        "scout_node",
        "validate_node",
        "analyst_node",
        "retrieve_node",
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
        knowledge_base: KnowledgeLike | None = None,
        tracer: LLMTracer | None = None,
    ) -> None:
        self.scout = scout
        self.analyst = analyst
        self.guide = guide
        self.knowledge_base = knowledge_base
        self.tracer = tracer
        self.output_root = output_root
        self.app: Any = self._build_graph().compile()

    async def run(
        self,
        city: str,
        persona_type: PersonaType | str,
        top_n: int = 10,
        output_root: Path | None = None,
    ) -> list[Deal]:
        persona = PersonaType(persona_type)
        trace_id = self.tracer.start_trace(
            "graph_pipeline",
            {"city": city, "persona": persona.value, "top_n": top_n},
        ) if self.tracer else None
        pipeline_started_at = perf_counter()
        search_log = SearchLog(
            city=city,
            persona=persona.value,
            started_at=datetime.now(UTC),
            status="started",
        )
        await asyncio.to_thread(save_search_log, search_log)
        original_output_root = self.output_root
        if output_root is not None:
            self.output_root = output_root
        try:
            result = await self.app.ainvoke(self._initial_state(city, persona, top_n, trace_id))
        except Exception as exc:
            search_log.finished_at = datetime.now(UTC)
            search_log.status = "failed"
            search_log.error_messages = str(exc)
            await asyncio.to_thread(save_search_log, search_log)
            if self.tracer and trace_id:
                self.tracer.end_trace(
                    trace_id,
                    "failed",
                    {
                        "error": str(exc),
                        "duration_ms": _elapsed_ms(pipeline_started_at),
                    },
                )
            raise
        finally:
            self.output_root = original_output_root
        ranked = result.get("ranked_deals", [])
        deals = list(ranked) if isinstance(ranked, list) else []
        errors = result.get("errors", [])
        search_log.finished_at = datetime.now(UTC)
        search_log.status = "success"
        search_log.deal_count = len(deals)
        search_log.error_messages = (
            json.dumps(errors, ensure_ascii=False) if isinstance(errors, list) and errors else None
        )
        await asyncio.to_thread(save_search_log, search_log)
        if self.tracer and trace_id:
            self.tracer.end_trace(
                trace_id,
                "success",
                {
                    "duration_ms": _elapsed_ms(pipeline_started_at),
                    "deal_count": len(deals),
                    "error_count": len(errors) if isinstance(errors, list) else 0,
                },
            )
        return deals

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
            await asyncio.to_thread(save_deals, ranked)
            return ranked
        return all_deals

    async def scout_node(self, state: PipelineState) -> dict[str, list[Deal] | list[str]]:
        span_id, started_at = self._start_node_span(
            state,
            "scout_node",
            {"city": state["city"], "retry_count": state["retry_count"]},
        )
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
            self._end_node_span(span_id, {"error": str(exc)}, started_at)
            return {
                "raw_deals": [],
                "errors": [*state["errors"], f"scout_node failed: {exc}"],
            }
        output: dict[str, list[Deal] | list[str]] = {"raw_deals": raw_deals}
        self._end_node_span(span_id, {"deal_count": len(raw_deals)}, started_at)
        return output

    async def validate_node(self, state: PipelineState) -> dict[str, list[Deal] | list[str]]:
        span_id, started_at = self._start_node_span(
            state,
            "validate_node",
            {"raw_deal_count": len(state["raw_deals"])},
        )
        result = validate_deals(state["raw_deals"])
        if result.invalid_deals:
            invalid_deals = [item[0] for item in result.invalid_deals]
            validation_errors = {item[0].id: item[1] for item in result.invalid_deals}
            await asyncio.to_thread(
                save_deals,
                invalid_deals,
                is_valid=False,
                validation_errors=validation_errors,
            )
        output: dict[str, list[Deal] | list[str]] = {
            "validated_deals": result.valid_deals,
            "errors": [*state["errors"], *result.errors],
        }
        self._end_node_span(
            span_id,
            {
                "valid_count": len(result.valid_deals),
                "invalid_count": len(result.invalid_deals),
            },
            started_at,
        )
        return output

    async def analyst_node(self, state: PipelineState) -> dict[str, list[Deal] | list[str]]:
        span_id, started_at = self._start_node_span(
            state,
            "analyst_node",
            {"validated_deal_count": len(state["validated_deals"])},
        )
        try:
            ranked = await self.analyst.analyze(
                state["validated_deals"],
                state["persona"],
                top_n=state["top_n"],
            )
        except Exception as exc:
            logger.exception("Analyst node failed")
            self._end_node_span(span_id, {"error": str(exc)}, started_at)
            return {
                "ranked_deals": [],
                "errors": [*state["errors"], f"analyst_node failed: {exc}"],
            }
        self._end_node_span(span_id, {"ranked_count": len(ranked)}, started_at)
        return {"ranked_deals": ranked}

    async def retrieve_node(self, state: PipelineState) -> dict[str, dict[str, str] | list[str]]:
        span_id, started_at = self._start_node_span(
            state,
            "retrieve_node",
            {"deal_ids": [deal.id for deal in state["ranked_deals"][:3]]},
        )
        if self.knowledge_base is None:
            self._end_node_span(span_id, {"knowledge_context": {}}, started_at)
            return {"knowledge_context": {}}
        knowledge_context: dict[str, str] = {}
        errors = list(state["errors"])
        for deal in state["ranked_deals"][:3]:
            try:
                chunks = self.knowledge_base.search(deal.destination_city, top_k=5)
            except Exception as exc:
                logger.exception("Knowledge retrieval failed for deal id=%s", deal.id)
                errors.append(f"retrieve_node failed for {deal.id}: {exc}")
                continue
            knowledge_context[deal.id] = "\n\n".join(chunks)
        output: dict[str, dict[str, str] | list[str]] = {
            "knowledge_context": knowledge_context,
            "errors": errors,
        }
        self._end_node_span(span_id, {"context_count": len(knowledge_context)}, started_at)
        return output

    async def guide_node(self, state: PipelineState) -> dict[str, dict[str, str] | list[str]]:
        span_id, started_at = self._start_node_span(
            state,
            "guide_node",
            {"deal_ids": [deal.id for deal in state["ranked_deals"][:3]]},
        )
        guides: dict[str, str] = {}
        errors = list(state["errors"])
        for deal in state["ranked_deals"][:3]:
            try:
                guides[deal.id] = await self.guide.generate(
                    deal,
                    state["persona"],
                    knowledge_context=state["knowledge_context"].get(deal.id, ""),
                )
            except Exception as exc:
                logger.exception("Guide node failed for deal id=%s", deal.id)
                errors.append(f"guide_node failed for {deal.id}: {exc}")
        output: dict[str, dict[str, str] | list[str]] = {"guides": guides, "errors": errors}
        self._end_node_span(span_id, {"guide_count": len(guides)}, started_at)
        return output

    async def save_node(self, state: PipelineState) -> dict[str, list[str]]:
        span_id, started_at = self._start_node_span(
            state,
            "save_node",
            {"ranked_deal_count": len(state["ranked_deals"])},
        )
        self._write_deals(state["ranked_deals"], self.output_root / "deals")
        self._write_guides(state["guides"], self.output_root / "guides")
        await asyncio.to_thread(save_deals, state["ranked_deals"])
        self._store_deal_history(state["ranked_deals"])
        if not state["raw_deals"]:
            output = {"errors": [*state["errors"], "no raw deals found after retry"]}
            self._end_node_span(span_id, output, started_at)
            return output
        if state["raw_deals"] and not state["validated_deals"]:
            output = {"errors": [*state["errors"], "no valid deals found after retry"]}
            self._end_node_span(span_id, output, started_at)
            return output
        self._end_node_span(span_id, {"saved_deal_count": len(state["ranked_deals"])}, started_at)
        return {}

    async def retry_node(
        self,
        state: PipelineState,
    ) -> dict[str, int | list[Deal] | list[str] | dict[str, str]]:
        span_id, started_at = self._start_node_span(
            state,
            "retry_node",
            {"retry_count": state["retry_count"]},
        )
        next_count = state["retry_count"] + 1
        message = (
            f"retry_node expanding search for {state['city']} "
            f"(attempt {next_count} of 1)"
        )
        logger.info(message)
        output: dict[str, int | list[Deal] | list[str] | dict[str, str]] = {
            "retry_count": next_count,
            "raw_deals": [],
            "validated_deals": [],
            "ranked_deals": [],
            "knowledge_context": {},
            "guides": {},
            "errors": [*state["errors"], message],
        }
        self._end_node_span(span_id, output, started_at)
        return output

    def graph_nodes(self) -> set[str]:
        return set(self.node_names)

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(PipelineState)
        graph.add_node("scout_node", self.scout_node)
        graph.add_node("validate_node", self.validate_node)
        graph.add_node("analyst_node", self.analyst_node)
        graph.add_node("retrieve_node", self.retrieve_node)
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
        graph.add_edge("analyst_node", "retrieve_node")
        graph.add_edge("retrieve_node", "guide_node")
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
        trace_id: str | None = None,
    ) -> PipelineState:
        return {
            "city": city,
            "persona": PersonaType(persona_type),
            "top_n": top_n,
            "raw_deals": [],
            "validated_deals": [],
            "ranked_deals": [],
            "knowledge_context": {},
            "guides": {},
            "errors": [],
            "retry_count": 0,
            "trace_id": trace_id,
        }

    def _write_deals(self, deals: list[Deal], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = build_deals_snapshot_path(
            output_dir,
            mode=getattr(self.scout, "mode", "run"),
        )
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

    def _store_deal_history(self, deals: list[Deal]) -> None:
        if self.knowledge_base is None:
            return
        for deal in deals:
            try:
                self.knowledge_base.add_deal_history(deal)
            except Exception:
                logger.exception("Failed to store deal history id=%s", deal.id)

    def _start_node_span(
        self,
        state: PipelineState,
        name: str,
        input_data: dict[str, Any],
    ) -> tuple[str | None, float]:
        if self.tracer is None:
            return None, perf_counter()
        span_id = self.tracer.start_span(state["trace_id"], name, input_data)
        return span_id, perf_counter()

    def _end_node_span(
        self,
        span_id: str | None,
        output_data: Any,
        started_at: float,
    ) -> None:
        if self.tracer is None or span_id is None:
            return
        self.tracer.end_span(
            span_id,
            output_data=output_data,
            token_usage=None,
            duration_ms=_elapsed_ms(started_at),
        )


def build_graph_pipeline(settings: Settings | None = None) -> GraphPipeline:
    resolved = settings or get_settings()
    tracer = _build_tracer(resolved)
    llm = build_llm(resolved, tracer=tracer)
    scout_llm = build_scout_llm(resolved, tracer=tracer)
    search = WebSearchTool(resolved)
    fetch = WebFetchTool(resolved)
    parser = PriceParserTool(llm)
    scout = ScoutAgent(
        scout_llm,
        [search, fetch, parser],
        mode=resolved.scout_mode,
        max_iterations=resolved.scout_max_iterations,
        max_tool_calls=resolved.scout_max_tool_calls,
    )
    analyst = AnalystAgent(llm, [])
    knowledge_base = _build_knowledge_base()
    guide = GuideAgent(llm, [search], knowledge_base=knowledge_base)
    return GraphPipeline(
        scout=scout,
        analyst=analyst,
        guide=guide,
        knowledge_base=knowledge_base,
        tracer=tracer,
    )


def _build_knowledge_base() -> KnowledgeBase | None:
    try:
        return KnowledgeBase()
    except Exception:
        logger.exception("Knowledge base unavailable; continuing without RAG")
        return None


def _build_tracer(settings: Settings) -> LLMTracer:
    return LLMTracer(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def _elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000
