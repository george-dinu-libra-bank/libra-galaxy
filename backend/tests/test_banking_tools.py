import pytest

from app.core.security import Principal
from app.repositories.banking_read_repository import AccountRow
from app.tools.banking_tools import build_banking_tools

UTILIZATOR = Principal(user_id="u1", role="customer", permissions={"accounts:read"})


class BankingRepoFals:
    def __init__(self, accounts):
        self._accounts = accounts

    def list_accounts(self, user_id):
        return self._accounts

    def list_recent_transactions(self, user_id, limit=50):
        return []


def _tool(nume):
    tools = build_banking_tools(
        BankingRepoFals(
            [
                AccountRow(
                    id="a1", name="Cont curent", iban="RO49AAAA1B31007593840000",
                    balance=100.0, currency="RON", created_at="2026-01-01T00:00:00+00:00",
                )
            ]
        )
    )
    return next(t for t in tools if t.name == nume)


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
