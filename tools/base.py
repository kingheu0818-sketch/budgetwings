from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolOutput(BaseModel):
    success: bool
    data: dict[str, Any] | list[Any] | str | int | float | None = None
    error: str | None = None


class BaseTool(ABC):
    name: str
    description: str
    input_model: type[ToolInput] = ToolInput

    @abstractmethod
    async def execute(self, input: ToolInput) -> ToolOutput:
        """Run the tool."""

    def to_schema(self, provider: Literal["claude", "openai"] = "claude") -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        if provider == "claude":
            return {
                "name": self.name,
                "description": self.description,
                "input_schema": schema,
            }
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }
