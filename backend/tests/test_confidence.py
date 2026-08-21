from app.agents.base import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM, confidence_from_tool_results
from app.tools.base import ToolResult


def _result(success: bool) -> ToolResult:
    return ToolResult(tool_name="get_accounts", success=success, data={} if success else None)


def test_no_tools_means_no_confidence_claim():
    assert confidence_from_tool_results([]) is None


def test_all_tools_succeeded_is_high_confidence():
    assert confidence_from_tool_results([_result(True), _result(True)]) == CONFIDENCE_HIGH


def test_partial_success_is_medium_confidence():
    assert confidence_from_tool_results([_result(True), _result(False)]) == CONFIDENCE_MEDIUM


def test_all_tools_failed_is_low_confidence():
    assert confidence_from_tool_results([_result(False), _result(False)]) == CONFIDENCE_LOW
