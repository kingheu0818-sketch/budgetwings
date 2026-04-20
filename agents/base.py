from __future__ import annotations

from pathlib import Path
from typing import Literal

from llm.base import LLMAdapter
from tools.base import BaseTool


class AgentError(RuntimeError):
    pass


class BaseAgent:
    name: str

    def __init__(self, llm: LLMAdapter, tools: list[BaseTool]) -> None:
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}

    def tool_schemas(
        self,
        provider: Literal["claude", "openai"] = "claude",
    ) -> list[dict[str, object]]:
        return [tool.to_schema(provider) for tool in self.tools.values()]

    def require_tool(self, name: str) -> BaseTool:
        tool = self.tools.get(name)
        if tool is None:
            msg = f"{self.name} requires tool: {name}"
            raise AgentError(msg)
        return tool


def load_prompt(name: str) -> str:
    return Path("prompts", f"{name}.md").read_text(encoding="utf-8")
