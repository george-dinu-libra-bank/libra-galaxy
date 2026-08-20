import pytest

from app.core.security import Principal
from app.tools.base import RiskLevel, SideEffect, ToolDefinition
from app.tools.eligibility import check_eligibility


async def _noop_callback(_principal, _args):
    return {}


def _tool(**overrides) -> ToolDefinition:
    defaults = dict(
        name="get_accounts",
        description="test",
        callback=_noop_callback,
        allowed_agents=frozenset({"financial_advisor"}),
        required_permissions=frozenset({"accounts:read"}),
        side_effect=SideEffect.READ_ONLY,
        risk_level=RiskLevel.LOW,
    )
    defaults.update(overrides)
    return ToolDefinition(**defaults)


def _principal(permissions: set[str]) -> Principal:
    return Principal(user_id="u1", role="customer", permissions=permissions)


def test_eligible_when_agent_permission_and_risk_match():
    tool = _tool()
    result = check_eligibility(tool, "financial_advisor", _principal({"accounts:read"}), RiskLevel.LOW)
    assert result.eligible


def test_not_eligible_for_unlisted_agent():
    tool = _tool()
    result = check_eligibility(tool, "engagement", _principal({"accounts:read"}), RiskLevel.LOW)
    assert not result.eligible


def test_not_eligible_without_required_permission():
    tool = _tool()
    result = check_eligibility(tool, "financial_advisor", _principal(set()), RiskLevel.LOW)
    assert not result.eligible


def test_not_eligible_when_tool_risk_exceeds_ceiling():
    tool = _tool(risk_level=RiskLevel.HIGH)
    result = check_eligibility(tool, "financial_advisor", _principal({"accounts:read"}), RiskLevel.LOW)
    assert not result.eligible


def test_mutating_tool_without_confirmation_fails_to_build():
    with pytest.raises(ValueError):
        _tool(side_effect=SideEffect.MUTATES, requires_confirmation=False)


def test_mutating_tool_with_confirmation_builds_fine():
    tool = _tool(side_effect=SideEffect.MUTATES, requires_confirmation=True, risk_level=RiskLevel.HIGH)
    assert tool.requires_confirmation
