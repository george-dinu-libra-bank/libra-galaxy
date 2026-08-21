"""Executie paralela cu timeout, barieta pentru mutatii (docs/AI_ARCHITECTURE.md #3).

Eligibilitatea e reverificata aici, chiar daca agentul a ales tool-ul deja o
data — un plan construit mai devreme in tura nu poate strecura un tool
neeligibil.
"""

from __future__ import annotations

import asyncio
import time

from app.core.security import Principal
from app.tools.base import RiskLevel, SelectedTool, SideEffect, ToolResult
from app.tools.eligibility import check_eligibility
from app.tools.registry import ToolRegistry

DEFAULT_TIMEOUT_SECONDS = 15.0


async def _run_one(
    selected: SelectedTool, tool_def, principal: Principal, timeout: float
) -> ToolResult:
    started = time.perf_counter()
    try:
        data = await asyncio.wait_for(tool_def.callback(principal, selected.args), timeout=timeout)
        return ToolResult(
            tool_name=selected.name, success=True, data=data, duration_ms=int((time.perf_counter() - started) * 1000)
        )
    except asyncio.TimeoutError:
        return ToolResult(
            tool_name=selected.name, success=False, error="TOOL_TIMEOUT",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:  # tool-urile nu trebuie sa opreasca toata tura
        return ToolResult(
            tool_name=selected.name, success=False, error=str(exc),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


async def execute_tools(
    selections: list[SelectedTool],
    *,
    agent_id: str,
    principal: Principal,
    risk_ceiling: RiskLevel,
    registry: ToolRegistry,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[ToolResult]:
    reads_and_compute: list[tuple[SelectedTool, object]] = []
    mutations: list[tuple[SelectedTool, object]] = []
    results: list[ToolResult] = []

    for selection in selections:
        tool_def = registry.get(selection.name)
        if tool_def is None:
            results.append(ToolResult(tool_name=selection.name, success=False, error="TOOL_NOT_ELIGIBLE"))
            continue

        eligibility = check_eligibility(tool_def, agent_id, principal, risk_ceiling)
        if not eligibility.eligible:
            results.append(ToolResult(tool_name=selection.name, success=False, error="TOOL_NOT_ELIGIBLE"))
            continue

        if tool_def.side_effect in (SideEffect.PREPARES_MUTATION, SideEffect.MUTATES):
            mutations.append((selection, tool_def))
        else:
            reads_and_compute.append((selection, tool_def))

    if reads_and_compute:
        parallel_results = await asyncio.gather(
            *(_run_one(selection, tool_def, principal, timeout) for selection, tool_def in reads_and_compute)
        )
        results.extend(parallel_results)

    # Bariera: mutatiile ruleaza singure, dupa ce toate citirile s-au terminat —
    # nu exista tool-uri de mutatie in acest MVP, dar structura ramane corecta
    # daca una apare mai tarziu.
    for selection, tool_def in mutations:
        results.append(await _run_one(selection, tool_def, principal, timeout))

    return results
