import re

import pytest

from app.core.security import Principal
from app.repositories.banking_read_repository import AccountRow
from app.tools.banking_tools import build_banking_tools

_FULL_IBAN = re.compile(r"^[A-Za-z]{2}\d{2}[A-Za-z0-9]{10,30}$")

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
                    balance=100.0, created_at="2026-01-01T00:00:00+00:00",
                )
            ]
        )
    )
    return next(t for t in tools if t.name == nume)


@pytest.mark.anyio
async def test_get_accounts_never_returns_a_full_iban():
    rezultat = await _tool("get_accounts").callback(UTILIZATOR, {})

    for cont in rezultat["accounts"]:
        assert not _FULL_IBAN.match(cont["iban"]), f"IBAN nemascat: {cont['iban']}"
        assert "•" in cont["iban"]


@pytest.mark.anyio
async def test_get_accounts_keeps_last_four_characters_visible():
    rezultat = await _tool("get_accounts").callback(UTILIZATOR, {})

    assert rezultat["accounts"][0]["iban"].endswith("0000")
