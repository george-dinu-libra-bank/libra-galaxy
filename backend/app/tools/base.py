"""Definitia unui tool (docs/AI_ARCHITECTURE.md #3, ARCHITECTURE.md #12) — singura punte agent -> aplicatie."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

from app.core.security import Principal


class SideEffect(str, Enum):
    READ_ONLY = "read_only"
    COMPUTE = "compute"
    PREPARES_MUTATION = "prepares_mutation"
    MUTATES = "mutates"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    data: dict | None = None
    error: str | None = None
    duration_ms: int = 0


@dataclass(frozen=True)
class SelectedTool:
    """O alegere de tool facuta de agent, cu motivul — auditabil (docs/SECURITY.md #2)."""

    name: str
    args: dict
    reason: str


ToolCallback = Callable[[Principal, dict], Awaitable[dict]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    callback: ToolCallback
    allowed_agents: frozenset[str]
    required_permissions: frozenset[str]
    side_effect: SideEffect
    risk_level: RiskLevel
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if self.side_effect == SideEffect.MUTATES and not self.requires_confirmation:
            raise ValueError(f"Tool-ul de mutatie '{self.name}' trebuie sa ceara confirmare.")
