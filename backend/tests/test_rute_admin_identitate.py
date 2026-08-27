"""Id-ul administratorului ajunge la depozit asa cum vine, nu reambalat.

`UserContext.user_id` e DEJA `UUID` (api/dependencies.py). Patru rute il treceau
prin `UUID(...)` inca o data, ceea ce arunca:

    AttributeError: 'UUID' object has no attribute 'replace'

Adica 500 la fiecare apasare pe „Aproba" — si nu doar pe fluxul nou de inchidere
a contului, ci si pe cel de stergere a clientului, scris runda trecuta. Nimic
n-a semnalat-o: `UUID(x)` e valid la typecheck cand `x` e `Any`, iar testele nu
chemau rutele de admin.

Testele de aici cheama chiar functiile de ruta, cu un depozit fals, si se uita
la ce a primit el.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.api.routes import admin as rute_admin
from app.schemas.admin import DecizieInchidereRequest, DecizieStergereRequest

ID_ADMIN = uuid4()
ID_CERERE = uuid4()


@dataclass
class _UserContextFals:
    """Aceeasi forma ca `api/dependencies.UserContext`: user_id e UUID."""

    user_id: UUID
    access_token: str = "token"


class _DepozitFals:
    def __init__(self, *_args, **_kwargs) -> None:
        self.primit: dict = {}

    async def decide_inchidere_cont(self, id_cerere, id_admin, aproba, **rest):
        self.primit = {"id_cerere": id_cerere, "id_admin": id_admin, "aproba": aproba, **rest}
        return {
            "id": ID_CERERE, "id_utilizator": uuid4(), "id_cont": uuid4(),
            "status": "aprobata", "creat_la": "2026-08-26T10:00:00+00:00",
        }

    async def decide_stergere(self, id_cerere, id_admin, aproba, motiv):
        self.primit = {"id_cerere": id_cerere, "id_admin": id_admin}
        return {
            "id": ID_CERERE, "id_utilizator": uuid4(), "status": "aprobata",
            "creat_la": "2026-08-26T10:00:00+00:00",
        }


@pytest.fixture
def depozit(monkeypatch) -> _DepozitFals:
    fals = _DepozitFals()
    monkeypatch.setattr(rute_admin, "AdminRepository", lambda _client: fals)
    return fals


async def test_inchiderea_primeste_uuid_ul_adminului_neatins(depozit) -> None:
    await rute_admin.decide_inchidere_cont(
        ID_CERERE,
        DecizieInchidereRequest(aproba=True),
        administrator=_UserContextFals(user_id=ID_ADMIN),
        client=object(),
    )

    assert depozit.primit["id_admin"] == ID_ADMIN
    assert isinstance(depozit.primit["id_admin"], UUID)


async def test_stergerea_primeste_uuid_ul_adminului_neatins(depozit) -> None:
    """Acelasi defect, pe fluxul scris runda trecuta."""
    await rute_admin.decide_stergere(
        ID_CERERE,
        DecizieStergereRequest(aproba=True),
        administrator=_UserContextFals(user_id=ID_ADMIN),
        client=object(),
    )

    assert depozit.primit["id_admin"] == ID_ADMIN


def test_user_context_chiar_are_uuid() -> None:
    """Daca tipul asta devine `str` intr-o zi, testele de mai sus trec degeaba —
    deci se verifica si premisa lor."""
    from typing import get_type_hints

    from app.api.dependencies import UserContext

    # `get_type_hints`, nu `__annotations__`: modulul are
    # `from __future__ import annotations`, deci adnotarile sunt siruri de
    # caractere si comparatia directa ar reusi mereu, pe nimic.
    assert get_type_hints(UserContext)["user_id"] is UUID
