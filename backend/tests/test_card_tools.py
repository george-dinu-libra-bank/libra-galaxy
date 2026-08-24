from uuid import uuid4

import pytest

from app.core.security import Principal
from app.tools.card_tools import build_card_tools

UTILIZATOR = Principal(user_id=str(uuid4()), role="customer", permissions={"cards:read"})

_CARDURI_DIN_DB = [
    {
        "id": "c1", "sold_curent": 0.0, "is_blocked": False, "creat_la": "2026-01-01T00:00:00+00:00",
        "data_expirare": "12/29", "card_style": "gold",
        # Campuri care nu ar trebui niciodata citite de CardRepository real, dar
        # daca ar aparea aici oricum (regresie), testul de mai jos le prinde.
        "numar_card": "4111111111111111", "ccv": "123",
    },
]


class CardRepoFals:
    def __init__(self, cards):
        self._cards = cards

    async def ale_utilizatorului(self, user_id):
        return self._cards


def _tool():
    tools = build_card_tools(CardRepoFals(_CARDURI_DIN_DB))
    return next(t for t in tools if t.name == "get_cards")


@pytest.mark.anyio
async def test_get_cards_returns_safe_fields():
    rezultat = await _tool().callback(UTILIZATOR, {})

    card = rezultat["cards"][0]
    assert card == {"id": "c1", "style": "gold", "expiry": "12/29", "is_blocked": False}


@pytest.mark.anyio
async def test_get_cards_never_returns_number_or_ccv():
    rezultat = await _tool().callback(UTILIZATOR, {})

    for card in rezultat["cards"]:
        assert "numar_card" not in card
        assert "ccv" not in card
        assert "4111111111111111" not in str(card)
