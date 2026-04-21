from __future__ import annotations

import asyncio
import json
from importlib import import_module
from typing import Any

from llm.base import ChatMessage, LLMAdapter, LLMError, ToolCallResult, ToolSchema
from observability.tracer import LLMTracer


class OpenAIAdapter(LLMAdapter):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        base_url: str | None = None,
        tracer: LLMTracer | None = None,
    ) -> None:
        super().__init__(model=model, timeout_seconds=timeout_seconds, tracer=tracer)
        try:
            openai = import_module("openai")
            client_kwargs: dict[str, Any] = {
                "api_key": api_key,
                "timeout": timeout_seconds,
            }
            if base_url:
                client_kwargs["base_url"] = base_url
            self._client = openai.AsyncOpenAI(**client_kwargs)
        except Exception as exc:  # pragma: no cover - exercised only without optional SDK.
            msg = "openai SDK is required for OpenAIAdapter"
            raise LLMError(msg) from exc

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
        span_id, started_at = self._start_llm_span(
            "openai.chat",
            {"messages": messages, "tools": tools or []},
        )
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools or None,
                ),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            self._end_llm_span(span_id, {"error": str(exc)}, started_at=started_at)
            msg = "OpenAI chat request failed"
            raise LLMError(msg) from exc

        output = self._message_content_to_text(response.choices[0].message)
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
            "openai.chat_with_tools",
            {"messages": messages, "tools": tools},
        )
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                ),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            self._end_llm_span(span_id, {"error": str(exc)}, started_at=started_at)
            msg = "OpenAI function-calling request failed"
            raise LLMError(msg) from exc

        message = response.choices[0].message
        result = {
            "provider": "openai",
            "content": self._message_content_to_text(message),
            "tool_calls": [self._tool_call_to_dict(call) for call in message.tool_calls or []],
        }
        self._end_llm_span(
            span_id,
            result,
            token_usage=self._usage_to_dict(response),
            started_at=started_at,
        )
        return result

    async def extract_structured(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        schema_name: str,
        schema_description: str,
    ) -> dict[str, Any]:
        span_id, started_at = self._start_llm_span(
            "openai.extract_structured",
            {
                "messages": messages,
                "schema_name": schema_name,
                "schema_description": schema_description,
            },
        )
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": schema,
                            "strict": True,
                        },
                    },
                ),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            self._end_llm_span(span_id, {"error": str(exc)}, started_at=started_at)
            msg = "OpenAI structured extraction request failed"
            raise LLMError(msg) from exc

        message = response.choices[0].message
        parsed = getattr(message, "parsed", None)
        try:
            if isinstance(parsed, dict):
                structured = parsed
            else:
                content = self._message_content_to_text(message)
                structured = json.loads(content)
        except Exception as exc:
            self._end_llm_span(
                span_id,
                {"error": f"Invalid structured JSON: {exc}"},
                token_usage=self._usage_to_dict(response),
                started_at=started_at,
            )
            msg = "OpenAI returned invalid structured JSON"
            raise LLMError(msg) from exc

        self._end_llm_span(
            span_id,
            structured,
            token_usage=self._usage_to_dict(response),
            started_at=started_at,
        )
        return structured

    def _tool_call_to_dict(self, call: Any) -> dict[str, Any]:
        return {
            "id": getattr(call, "id", None),
            "type": getattr(call, "type", None),
            "function": {
                "name": getattr(call.function, "name", None),
                "arguments": getattr(call.function, "arguments", None),
            },
        }

    def _message_content_to_text(self, message: Any) -> str:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = getattr(item, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        parsed = getattr(message, "parsed", None)
        if parsed is not None:
            return str(parsed)
        return ""

    def _usage_to_dict(self, response: Any) -> dict[str, int] | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        return {
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "total_tokens": int(total_tokens or 0),
        }
