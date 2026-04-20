from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any

from observability.tracer import LLMTracer

ChatMessage = dict[str, Any]
ToolSchema = dict[str, Any]
ToolCallResult = dict[str, Any]


class LLMError(RuntimeError):
    pass


class LLMAdapter(ABC):
    def __init__(
        self,
        model: str,
        timeout_seconds: float = 60.0,
        tracer: LLMTracer | None = None,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.tracer = tracer

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        """Send messages and return plain text."""

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        """Send messages and return provider-specific tool-use metadata."""

    def _start_llm_span(self, name: str, input_data: dict[str, Any]) -> tuple[str | None, float]:
        if self.tracer is None:
            return None, perf_counter()
        payload = {"model": self.model, **input_data}
        span_id = self.tracer.start_span(self.tracer.current_trace_id, name, payload)
        return span_id, perf_counter()

    def _end_llm_span(
        self,
        span_id: str | None,
        output_data: Any,
        token_usage: dict[str, int] | None = None,
        started_at: float | None = None,
    ) -> None:
        if self.tracer is None or span_id is None:
            return
        duration_ms = (perf_counter() - started_at) * 1000 if started_at is not None else None
        self.tracer.end_span(
            span_id,
            output_data=output_data,
            token_usage=token_usage,
            duration_ms=duration_ms,
        )
