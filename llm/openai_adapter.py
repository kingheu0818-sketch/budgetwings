from __future__ import annotations

import asyncio
from importlib import import_module
from typing import Any

from llm.base import ChatMessage, LLMAdapter, LLMError, ToolCallResult, ToolSchema


class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 60.0) -> None:
        super().__init__(model=model, timeout_seconds=timeout_seconds)
        try:
            openai = import_module("openai")
            self._client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        except Exception as exc:  # pragma: no cover - exercised only without optional SDK.
            msg = "openai SDK is required for OpenAIAdapter"
            raise LLMError(msg) from exc

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> str:
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
            msg = "OpenAI chat request failed"
            raise LLMError(msg) from exc

        content = response.choices[0].message.content
        return content or ""

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema],
    ) -> ToolCallResult:
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
            msg = "OpenAI function-calling request failed"
            raise LLMError(msg) from exc

        message = response.choices[0].message
        return {
            "provider": "openai",
            "content": message.content,
            "tool_calls": [self._tool_call_to_dict(call) for call in message.tool_calls or []],
        }

    def _tool_call_to_dict(self, call: Any) -> dict[str, Any]:
        return {
            "id": getattr(call, "id", None),
            "type": getattr(call, "type", None),
            "function": {
                "name": getattr(call.function, "name", None),
                "arguments": getattr(call.function, "arguments", None),
            },
        }
