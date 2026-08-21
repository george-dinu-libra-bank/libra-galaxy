from __future__ import annotations

from app.tools.base import ToolDefinition


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def for_agent(self, agent_id: str) -> list[ToolDefinition]:
        return [tool for tool in self._tools.values() if agent_id in tool.allowed_agents]

    def all(self) -> list[ToolDefinition]:
        return list(self._tools.values())
