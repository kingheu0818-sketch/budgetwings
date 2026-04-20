from __future__ import annotations

import asyncio
from importlib import import_module
from typing import Any

from llm.base import ChatMessage, LLMAdapter, LLMError, ToolCallResult, ToolSchema
from observability.tracer import LLMTracer


class ClaudeAdapter(LLMAdapter):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        tracer: LLMTracer | None = None,
    ) -> None:
        super().__init__(model=model, timeout_seconds=timeout_seconds, tracer=tracer)
        try:
            anthropic = import_module("anthropic")
            self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_seconds)
        except Exception as exc:  # pragma: no cover - exercised only without optional SDK.
            msg = "anthropic SDK is required for ClaudeAdapter"
            raise LLMError(msg) from exc

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        span_id, started_at = self._start_llm_span(
            "claude.chat",
            {"messages": messages, "tools": tools or []},
        )
        system, user_messages = self._split_system_messages(messages)
        try:
            response = await asyncio.wait_for(
                self._client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=system or None,
                    messages=user_messages,
                    tools=tools or None,
                ),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            self._end_llm_span(span_id, {"error": str(exc)}, started_at=started_at)
            msg = "Claude chat request failed"
            raise LLMError(msg) from exc

        text_blocks: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_blocks.append(str(block.text))
        output = "\n".join(text_blocks)
        self._end_llm_span(
            span_id,
            {"content": output},
            token_usage=self._usage_to_dict(response),
            started_at=started_at,
        )
        return output

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
        span_id, started_at = self._start_llm_span(
            "claude.chat_with_tools",
            {"messages": messages, "tools": tools},
        )
        system, user_messages = self._split_system_messages(messages)
        try:
            response = await asyncio.wait_for(
                self._client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=system or None,
                    messages=user_messages,
                    tools=tools,
                ),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            self._end_llm_span(span_id, {"error": str(exc)}, started_at=started_at)
            msg = "Claude tool-use request failed"
            raise LLMError(msg) from exc

        result = {
            "provider": "claude",
            "stop_reason": response.stop_reason,
            "content": [self._block_to_dict(block) for block in response.content],
        }
        self._end_llm_span(
            span_id,
            result,
            token_usage=self._usage_to_dict(response),
            started_at=started_at,
        )
        return result

    def _block_to_dict(self, block: Any) -> dict[str, Any]:
        block_type = getattr(block, "type", "")
        if block_type == "tool_use":
            return {
                "type": "tool_use",
                "id": getattr(block, "id", None),
                "name": getattr(block, "name", None),
                "input": getattr(block, "input", None),
            }
        if block_type == "text":
            return {"type": "text", "text": getattr(block, "text", "")}
        return {"type": str(block_type), "raw": repr(block)}

    def _split_system_messages(
        self,
        messages: list[ChatMessage],
    ) -> tuple[str, list[ChatMessage]]:
        system_parts: list[str] = []
        user_messages: list[ChatMessage] = []
        for message in messages:
            if message.get("role") == "system":
                system_parts.append(str(message.get("content", "")))
            else:
                user_messages.append(message)
        return "\n\n".join(system_parts), user_messages

    def _usage_to_dict(self, response: Any) -> dict[str, int] | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        return {
            "prompt_tokens": int(input_tokens or 0),
            "completion_tokens": int(output_tokens or 0),
            "total_tokens": int((input_tokens or 0) + (output_tokens or 0)),
        }
