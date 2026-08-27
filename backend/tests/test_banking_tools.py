from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import Principal
from app.repositories.banking_read_repository import AccountRow, TransactionRow
from app.tools.banking_tools import build_banking_tools

UTILIZATOR = Principal(user_id="u1", role="customer", permissions={"accounts:read"})


class BankingRepoFals:
    def __init__(self, accounts=(), transactions=()):
        self._accounts = accounts
        self._transactions = transactions

    def list_accounts(self, user_id):
        return self._accounts

    def list_recent_transactions(self, user_id, limit=50):
        return self._transactions


def _tool(nume, transactions=()):
    tools = build_banking_tools(
        BankingRepoFals(
            accounts=[
                AccountRow(
                    id="a1", name="Cont curent", iban="RO49AAAA1B31007593840000",
                    balance=100.0, currency="RON", created_at="2026-01-01T00:00:00+00:00",
                )
            ],
            transactions=transactions,
        )
    )
    return next(t for t in tools if t.name == nume)


def _acum() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _acum_minus(zile: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=zile)).isoformat().replace("+00:00", "Z")


@pytest.mark.anyio
async def test_get_accounts_returns_the_full_iban():
    # Decizie explicita (GUARDRAILS.md #12): IBAN-ul propriu nu e un secret,
    # e deja aratat complet in restul aplicatiei (detalii-cont-drawer.tsx).
    rezultat = await _tool("get_accounts").callback(UTILIZATOR, {})

    assert rezultat["accounts"][0]["iban"] == "RO49AAAA1B31007593840000"


@pytest.mark.anyio
async def test_get_accounts_includes_currency():
    rezultat = await _tool("get_accounts").callback(UTILIZATOR, {})

    assert rezultat["accounts"][0]["currency"] == "RON"


@pytest.mark.anyio
async def test_find_transaction_for_receipt_matches_amount_and_category():
    tranzactii = [
        TransactionRow(
            id="tx1", amount=150.0, currency="RON", description="Cina la restaurant",
            created_at=_acum_minus(2), incoming=False, counterparty_name=None,
        ),
    ]

    rezultat = await _tool("find_transaction_for_receipt", tranzactii).callback(UTILIZATOR, {"suma": 150.0})

    assert len(rezultat["candidates"]) == 1
    assert rezultat["candidates"][0]["id"] == "tx1"
    assert rezultat["candidates"][0]["category"] == "restaurant"


@pytest.mark.anyio
async def test_find_transaction_for_receipt_ignores_incoming_transactions():
    tranzactii = [
        TransactionRow(
            id="tx1", amount=150.0, currency="RON", description="Salariu",
            created_at=_acum_minus(1), incoming=True, counterparty_name=None,
        ),
    ]

    rezultat = await _tool("find_transaction_for_receipt", tranzactii).callback(UTILIZATOR, {"suma": 150.0})

    assert rezultat["candidates"] == []


@pytest.mark.anyio
async def test_find_transaction_for_receipt_ignores_transactions_older_than_14_days():
    tranzactii = [
        TransactionRow(
            id="tx1", amount=150.0, currency="RON", description="Cina la restaurant",
            created_at=_acum_minus(20), incoming=False, counterparty_name=None,
        ),
    ]

    rezultat = await _tool("find_transaction_for_receipt", tranzactii).callback(UTILIZATOR, {"suma": 150.0})

    assert rezultat["candidates"] == []


@pytest.mark.anyio
async def test_find_transaction_for_receipt_without_amount_returns_no_candidates():
    rezultat = await _tool("find_transaction_for_receipt", []).callback(UTILIZATOR, {})

    assert rezultat["candidates"] == []


@pytest.mark.anyio
async def test_find_transaction_for_receipt_does_not_match_a_different_amount():
    tranzactii = [
        TransactionRow(
            id="tx1", amount=99.0, currency="RON", description="Cumparaturi",
            created_at=_acum(), incoming=False, counterparty_name=None,
        ),
    ]

    rezultat = await _tool("find_transaction_for_receipt", tranzactii).callback(UTILIZATOR, {"suma": 150.0})

    assert rezultat["candidates"] == []
