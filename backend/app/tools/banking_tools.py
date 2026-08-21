"""Tool-uri deterministe peste conturi/tranzactii reale — niciodata scriere.

Fabrica primeste repository-ul la construire (fara singleton la nivel de
modul), consistent cu compunerea din api/dependencies.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core.security import PERMISSION_ACCOUNTS_READ, Principal
from app.repositories.banking_read_repository import BankingReadRepository
from app.tools.base import RiskLevel, SideEffect, ToolDefinition

_ADVISOR_TOOLS_AGENTS = frozenset({"financial_advisor", "transaction_intelligence", "engagement"})


def build_banking_tools(repository: BankingReadRepository) -> list[ToolDefinition]:
    async def get_accounts(principal: Principal, _args: dict) -> dict:
        accounts = repository.list_accounts(principal.user_id)
        return {
            "accounts": [
                {"id": account.id, "name": account.name, "iban": account.iban, "balance": account.balance}
                for account in accounts
            ]
        }

    async def get_recent_transactions(principal: Principal, args: dict) -> dict:
        limit = min(int(args.get("limit", 20)), 100)
        transactions = repository.list_recent_transactions(principal.user_id, limit=limit)
        return {
            "transactions": [
                {
                    "id": tx.id,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "description": tx.description,
                    "created_at": tx.created_at,
                    "direction": "in" if tx.incoming else "out",
                    "counterparty_name": tx.counterparty_name,
                }
                for tx in transactions
            ]
        }

    async def get_spending_summary(principal: Principal, args: dict) -> dict:
        days = min(int(args.get("days", 30)), 365)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        transactions = repository.list_recent_transactions(principal.user_id, limit=500)

        totals_by_currency: dict[str, dict[str, float]] = defaultdict(lambda: {"in": 0.0, "out": 0.0})
        for tx in transactions:
            created_at = datetime.fromisoformat(tx.created_at.replace("Z", "+00:00"))
            if created_at < since:
                continue
            bucket = totals_by_currency[tx.currency]
            bucket["in" if tx.incoming else "out"] += tx.amount

        return {
            "period_days": days,
            "by_currency": [
                {"currency": currency, "total_in": round(values["in"], 2), "total_out": round(values["out"], 2)}
                for currency, values in totals_by_currency.items()
            ],
        }

    return [
        ToolDefinition(
            name="get_accounts",
            description="Returneaza conturile bancare ale utilizatorului curent, cu sold.",
            callback=get_accounts,
            allowed_agents=_ADVISOR_TOOLS_AGENTS,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="get_recent_transactions",
            description="Returneaza ultimele tranzactii ale utilizatorului curent.",
            callback=get_recent_transactions,
            allowed_agents=frozenset({"transaction_intelligence", "financial_advisor"}),
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="get_spending_summary",
            description="Aduna intrarile si iesirile din ultimele N zile, pe valuta.",
            callback=get_spending_summary,
            allowed_agents=frozenset({"transaction_intelligence", "financial_advisor"}),
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.COMPUTE,
            risk_level=RiskLevel.LOW,
        ),
    ]
