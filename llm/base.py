from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

ChatMessage = dict[str, Any]
ToolSchema = dict[str, Any]
ToolCallResult = dict[str, Any]


class LLMError(RuntimeError):
    pass


class LLMAdapter(ABC):
    def __init__(self, model: str, timeout_seconds: float = 60.0) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

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
