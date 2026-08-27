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
from app.tools.categorii_tranzactii import categorizeaza

_ADVISOR_TOOLS_AGENTS = frozenset({"financial_advisor", "transaction_intelligence", "engagement"})


def build_banking_tools(repository: BankingReadRepository) -> list[ToolDefinition]:
    async def get_accounts(principal: Principal, _args: dict) -> dict:
        # IBAN complet, nemascat: e contul propriu al utilizatorului autentificat,
        # aratat deja complet in restul aplicatiei (ex. detalii-cont-drawer.tsx) —
        # nu e un secret ca un CVV/PIN, e un numar de rutare facut sa fie dat mai
        # departe. Deciza explicita, GUARDRAILS.md #12.
        accounts = repository.list_accounts(principal.user_id)
        return {
            "accounts": [
                {
                    "id": account.id, "name": account.name, "iban": account.iban,
                    "balance": account.balance, "currency": account.currency,
                    "is_blocked": account.blocked,
                }
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
                    # Determinist (tools/categorii_tranzactii.py), niciodata ghicit de model.
                    "category": categorizeaza(tx.description, tx.counterparty_name),
                }
                for tx in transactions
            ]
        }

    async def find_transaction_for_receipt(principal: Principal, args: dict) -> dict:
        suma = args.get("suma")
        if suma is None:
            return {"candidates": []}

        # 14 zile, nu o fereastra mai larga: o chitanta se leaga de o plata
        # recenta, nu de istoricul intreg — reduce riscul unei potriviri
        # intamplatoare intre doua plati diferite cu aceeasi suma.
        since = datetime.now(timezone.utc) - timedelta(days=14)
        transactions = repository.list_recent_transactions(principal.user_id, limit=200)

        candidates = []
        for tx in transactions:
            if tx.incoming:
                continue
            if round(tx.amount, 2) != round(float(suma), 2):
                continue
            created_at = datetime.fromisoformat(tx.created_at.replace("Z", "+00:00"))
            if created_at < since:
                continue
            candidates.append({
                "id": tx.id,
                "amount": tx.amount,
                "currency": tx.currency,
                "description": tx.description,
                "created_at": tx.created_at,
                "counterparty_name": tx.counterparty_name,
                "category": categorizeaza(tx.description, tx.counterparty_name),
            })

        return {"candidates": candidates}

    async def get_spending_summary(principal: Principal, args: dict) -> dict:
        days = min(int(args.get("days", 30)), 365)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        transactions = repository.list_recent_transactions(principal.user_id, limit=500)

        totals_by_currency: dict[str, dict[str, float]] = defaultdict(lambda: {"in": 0.0, "out": 0.0})
        totals_by_category: dict[str, float] = defaultdict(float)
        for tx in transactions:
            created_at = datetime.fromisoformat(tx.created_at.replace("Z", "+00:00"))
            if created_at < since:
                continue
            bucket = totals_by_currency[tx.currency]
            bucket["in" if tx.incoming else "out"] += tx.amount
            if not tx.incoming:
                categorie = categorizeaza(tx.description, tx.counterparty_name)
                totals_by_category[categorie] += tx.amount

        return {
            "period_days": days,
            "by_currency": [
                {"currency": currency, "total_in": round(values["in"], 2), "total_out": round(values["out"], 2)}
                for currency, values in totals_by_currency.items()
            ],
            # Doar cheltuieli (iesiri) — amestecarea valutelor e o aproximare
            # acceptabila aici, e un rezumat orientativ, nu o suma exacta.
            "spending_by_category": [
                {"category": categorie, "total_out": round(suma, 2)}
                for categorie, suma in sorted(totals_by_category.items(), key=lambda item: -item[1])
            ],
        }

    return [
        ToolDefinition(
            name="get_accounts",
            description=(
                "Returneaza conturile bancare ale utilizatorului curent, cu sold si cu "
                "`is_blocked` — daca banca a oprit iesirile din acel cont."
            ),
            callback=get_accounts,
            allowed_agents=_ADVISOR_TOOLS_AGENTS,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="get_recent_transactions",
            description=(
                "Returneaza ultimele tranzactii ale utilizatorului curent, fiecare cu o categorie "
                "determinista (restaurant, cumparaturi, utilitati, transfer, masina, locuinta, "
                "salariu, sanatate, abonamente, altele)."
            ),
            callback=get_recent_transactions,
            allowed_agents=frozenset({"transaction_intelligence", "financial_advisor"}),
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="find_transaction_for_receipt",
            description=(
                "Cauta o tranzactie de-a utilizatorului care se potriveste cu suma mentionata, in "
                "ultimele 14 zile. Foloseste cand utilizatorul spune ca un atasament corespunde unei "
                "plati reale si vrea sa il lege de ea."
            ),
            callback=find_transaction_for_receipt,
            allowed_agents=frozenset({"transaction_intelligence"}),
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="get_spending_summary",
            description=(
                "Aduna intrarile si iesirile din ultimele N zile, pe valuta, si cheltuielile "
                "pe categorie determinista (restaurant, cumparaturi, utilitati etc.)."
            ),
            callback=get_spending_summary,
            allowed_agents=frozenset({"transaction_intelligence", "financial_advisor"}),
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.COMPUTE,
            risk_level=RiskLevel.LOW,
        ),
    ]
