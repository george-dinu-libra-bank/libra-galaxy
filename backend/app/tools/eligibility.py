"""Eligibilitate decisa in afara modelului, reverificata la executie (docs/SECURITY.md #2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.security import Principal
from app.tools.base import RiskLevel, ToolDefinition

_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reason: str


def check_eligibility(
    tool: ToolDefinition, agent_id: str, principal: Principal, risk_ceiling: RiskLevel
) -> EligibilityResult:
    if agent_id not in tool.allowed_agents:
        return EligibilityResult(False, f"'{tool.name}' nu e alocat agentului '{agent_id}'.")

    missing = tool.required_permissions - principal.permissions
    if missing:
        return EligibilityResult(False, f"Lipsesc permisiunile: {', '.join(sorted(missing))}.")

    if _RISK_ORDER[tool.risk_level] > _RISK_ORDER[risk_ceiling]:
        return EligibilityResult(False, f"Riscul tool-ului ({tool.risk_level.value}) depaseste plafonul turei.")

    return EligibilityResult(True, "eligibil")


def eligible_tools(
    tools: list[ToolDefinition], agent_id: str, principal: Principal, risk_ceiling: RiskLevel
) -> list[ToolDefinition]:
    return [tool for tool in tools if check_eligibility(tool, agent_id, principal, risk_ceiling).eligible]
