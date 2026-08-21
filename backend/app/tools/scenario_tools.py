"""Simulare what-if determinista — aritmetica in bani (integer), nu in virgula mobila.

Modelul e simplu deliberat: depunere lunara fixa, dobanda anuala optionala,
compusa lunar. Complexitatea (CashPlay complet) e scop viitor (PROJECT_CONTEXT.md #29);
azi doar proiectia de baza cere agentul financial_advisor sa explice, nu sa calculeze.
"""

from __future__ import annotations

from app.core.security import PERMISSION_ACCOUNTS_READ, Principal
from app.tools.base import RiskLevel, SideEffect, ToolDefinition

MAX_MONTHS = 60


def _to_bani(amount: float) -> int:
    return round(amount * 100)


def _project(starting_balance: float, monthly_amount: float, months: int, annual_rate_percent: float) -> list[dict]:
    balance_bani = _to_bani(starting_balance)
    monthly_deposit_bani = _to_bani(monthly_amount)
    monthly_rate = annual_rate_percent / 100 / 12

    series = []
    for month in range(1, months + 1):
        balance_bani += monthly_deposit_bani
        if monthly_rate:
            balance_bani = round(balance_bani * (1 + monthly_rate))
        series.append({"month": month, "balance": balance_bani / 100})

    return series


async def run_scenario(_principal: Principal, args: dict) -> dict:
    months = max(1, min(int(args.get("months", 12)), MAX_MONTHS))
    monthly_amount = float(args.get("monthly_amount", 0))
    starting_balance = float(args.get("starting_balance", 0))
    annual_rate_percent = float(args.get("annual_rate_percent", 0))

    series = _project(starting_balance, monthly_amount, months, annual_rate_percent)

    return {
        "months": months,
        "monthly_amount": monthly_amount,
        "annual_rate_percent": annual_rate_percent,
        "final_balance": series[-1]["balance"] if series else starting_balance,
        "series": series,
    }


SCENARIO_TOOL = ToolDefinition(
    name="run_scenario",
    description="Proiecteaza soldul pe N luni, cu depuneri lunare fixe si dobanda anuala optionala.",
    callback=run_scenario,
    allowed_agents=frozenset({"financial_advisor"}),
    required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
    side_effect=SideEffect.COMPUTE,
    risk_level=RiskLevel.LOW,
)
