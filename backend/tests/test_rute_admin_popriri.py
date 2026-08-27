"""Rutele de poprire: ce ajunge la depozit si ce se intampla la refuzul bazei.

Doua lucruri se verifica aici, si niciunul nu se vede din citirea codului.

1. `UserContext.user_id` e DEJA `UUID` — lectia din
   `test_rute_admin_identitate.py`, unde patru rute il mai treceau o data prin
   `UUID(...)` si dadeau 500 la fiecare apasare pe „Aproba". Rutele noi merg pe
   acelasi drum, deci merita aceeasi plasa.

2. Un refuz ASTEPTAT al bazei (poprirea e deja stinsa, clientul n-are bani) nu
   trebuie sa iasa 500. Fara traducerea din `MESAJE_POPRIRE`, in panou ar scrie
   „a aparut o eroare neasteptata" pentru o situatie perfect normala — exact
   tiparul reparat de commit-ul „Deciziile din panoul de admin nu mai dau 500".

Barierele adevarate (cat e indisponibil, cat se poate lua) stau in RPC-urile din
0043 si sunt verificate direct pe baza, nu de aici.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import admin as rute_admin
from app.schemas.admin import (
    IncaseazaPoprireRequest,
    InstituiePoprireRequest,
    RidicaPoprireRequest,
    StorneazaPoprireRequest,
)

ID_ADMIN = uuid4()
ID_POPRIRE = uuid4()
ID_CLIENT = uuid4()


@dataclass
class _UserContextFals:
    """Aceeasi forma ca `api/dependencies.UserContext`: user_id e UUID."""

    user_id: UUID
    access_token: str = "token"


def _rand_poprire(**peste) -> dict:
    baza = {
        "id": ID_POPRIRE,
        "id_utilizator": ID_CLIENT,
        "creditor": "BEJ Popescu",
        "dosar": "123/2026",
        "suma_totala": "5000.00",
        "suma_incasata": "0.00",
        "valuta": "RON",
        "status": "activa",
        "creat_la": "2026-08-27T10:00:00+00:00",
    }
    return {**baza, **peste}


class _EroareRpcFalsa(Exception):
    """Forma pe care o are o exceptie `postgrest`: codul in `message`."""

    def __init__(self, cod: str) -> None:
        super().__init__(cod)
        self.message = cod


class _DepozitFals:
    def __init__(self, *, ridica: str | None = None) -> None:
        self.primit: dict = {}
        self._ridica = ridica

    def _poate_ridica(self) -> None:
        if self._ridica:
            raise _EroareRpcFalsa(self._ridica)

    async def instituie_poprire(self, id_utilizator, creditor, suma, id_admin, **rest):
        self.primit = {
            "id_utilizator": id_utilizator,
            "creditor": creditor,
            "suma": suma,
            "id_admin": id_admin,
            **rest,
        }
        self._poate_ridica()
        return _rand_poprire()

    async def incaseaza_poprire(self, id_poprire, id_admin, suma=None):
        self.primit = {"id_poprire": id_poprire, "id_admin": id_admin, "suma": suma}
        self._poate_ridica()
        return _rand_poprire(suma_incasata="5000.00", status="stinsa")

    async def ridica_poprire(self, id_poprire, id_admin, motiv=None):
        self.primit = {"id_poprire": id_poprire, "id_admin": id_admin, "motiv": motiv}
        self._poate_ridica()
        return _rand_poprire(status="ridicata")


@pytest.fixture
def depozit(monkeypatch) -> _DepozitFals:
    fals = _DepozitFals()
    monkeypatch.setattr(rute_admin, "AdminRepository", lambda _client: fals)
    return fals


async def test_instituirea_trimite_uuid_urile_neatinse(depozit) -> None:
    raspuns = await rute_admin.instituie_poprire(
        InstituiePoprireRequest(
            id_utilizator=ID_CLIENT,
            creditor="BEJ Popescu",
            suma=Decimal("5000"),
            dosar="123/2026",
        ),
        administrator=_UserContextFals(user_id=ID_ADMIN),
        client=object(),
    )

    assert depozit.primit["id_admin"] == ID_ADMIN
    assert depozit.primit["id_utilizator"] == ID_CLIENT
    assert depozit.primit["dosar"] == "123/2026"
    assert raspuns.status == "activa"


async def test_incasarea_fara_suma_lasa_none(depozit) -> None:
    """Lipsa sumei inseamna „cat se poate acum" — se transmite ca atare, nu ca 0."""
    await rute_admin.incaseaza_poprire(
        ID_POPRIRE,
        IncaseazaPoprireRequest(),
        administrator=_UserContextFals(user_id=ID_ADMIN),
        client=object(),
    )

    assert depozit.primit["suma"] is None
    assert depozit.primit["id_admin"] == ID_ADMIN


async def test_ridicarea_duce_motivul_mai_departe(depozit) -> None:
    raspuns = await rute_admin.ridica_poprire(
        ID_POPRIRE,
        RidicaPoprireRequest(motiv="Contestatie admisa"),
        administrator=_UserContextFals(user_id=ID_ADMIN),
        client=object(),
    )

    assert depozit.primit["motiv"] == "Contestatie admisa"
    assert raspuns.status == "ridicata"


@pytest.mark.parametrize(
    ("cod", "stare"),
    [
        ("FONDURI_INSUFICIENTE", 409),
        ("POPRIRE_INCHEIATA", 409),
        ("POPRIRE_INEXISTENTA", 404),
        ("PESTE_RESTUL_DE_PLATA", 400),
    ],
)
async def test_refuzul_asteptat_nu_iese_500(monkeypatch, cod: str, stare: int) -> None:
    """Clientul fara bani nu e o defectiune a serverului."""
    fals = _DepozitFals(ridica=cod)
    monkeypatch.setattr(rute_admin, "AdminRepository", lambda _client: fals)

    with pytest.raises(HTTPException) as exc:
        await rute_admin.incaseaza_poprire(
            ID_POPRIRE,
            IncaseazaPoprireRequest(),
            administrator=_UserContextFals(user_id=ID_ADMIN),
            client=object(),
        )

    assert exc.value.status_code == stare
    assert "eroare neasteptata" not in str(exc.value.detail)


async def test_eroarea_neprevazuta_ramane_500(monkeypatch) -> None:
    """Ce nu e in dictionar NU trebuie sa arate ca un refuz prevazut."""
    fals = _DepozitFals(ridica="CEVA_CE_NU_STIM")
    monkeypatch.setattr(rute_admin, "AdminRepository", lambda _client: fals)

    with pytest.raises(HTTPException) as exc:
        await rute_admin.ridica_poprire(
            ID_POPRIRE,
            RidicaPoprireRequest(),
            administrator=_UserContextFals(user_id=ID_ADMIN),
            client=object(),
        )

    assert exc.value.status_code == 500


# -----------------------------------------------------------------------------
# Regresie: sumele vin in DOUA forme, dupa drum
#
# PostgREST serializeaza `numeric` ca SIR cand citesti tabela, dar ca NUMAR cand
# il intoarce un RPC. `PoprireResponse` declara doar `str`, deci:
#
#   ValidationError: suma_totala: Input should be a valid string
#     [input_value=1000000000.0, input_type=float]
#
# Efectul era pe dos decat cel util: lista mergea (era goala la prima incercare),
# iar INSTITUIREA dadea 500 dupa ce RPC-ul scrisese deja randul. Adica analistul
# vedea „eroare" si clientul ramanea cu o poprire reala pe cont.
#
# Testele cu depozit fals nu puteau prinde asta: ele intorceau siruri, fiindca
# asa le-am scris eu. Forma adevarata a venit din baza, la prima apasare reala.
# -----------------------------------------------------------------------------


def test_sumele_vin_ca_float_din_rpc() -> None:
    from app.schemas.admin import PoprireResponse

    raspuns = PoprireResponse(
        **_rand_poprire(suma_totala=1000000000.0, suma_incasata=0.0, disponibil=81.26)
    )

    assert raspuns.suma_totala == "1000000000.00"
    assert raspuns.suma_incasata == "0.00"
    assert raspuns.disponibil == "81.26"


def test_sumele_vin_ca_sir_din_tabela() -> None:
    """Cealalta forma trebuie sa treaca neschimbata."""
    from app.schemas.admin import PoprireResponse

    raspuns = PoprireResponse(**_rand_poprire(suma_totala="5000.00", suma_incasata="1250.50"))

    assert raspuns.suma_totala == "5000.00"
    assert raspuns.suma_incasata == "1250.50"


async def test_instituirea_nu_mai_crapa_pe_raspunsul_real(monkeypatch) -> None:
    """Ruta intreaga, cu forma pe care o intoarce chiar RPC-ul."""

    class _DepozitCuFloat(_DepozitFals):
        async def instituie_poprire(self, id_utilizator, creditor, suma, id_admin, **rest):
            return _rand_poprire(suma_totala=1000000000.0, suma_incasata=0.0)

    monkeypatch.setattr(rute_admin, "AdminRepository", lambda _client: _DepozitCuFloat())

    raspuns = await rute_admin.instituie_poprire(
        InstituiePoprireRequest(
            id_utilizator=ID_CLIENT, creditor="ANAF-Constanta", suma=Decimal("1000000000")
        ),
        administrator=_UserContextFals(user_id=ID_ADMIN),
        client=object(),
    )

    assert raspuns.suma_totala == "1000000000.00"


# -----------------------------------------------------------------------------
# Stornarea (0048): reverse-ul incasarii
# -----------------------------------------------------------------------------


async def test_stornarea_fara_suma_inseamna_tot(monkeypatch) -> None:
    class _DepozitStorno(_DepozitFals):
        async def storneaza_incasarea(self, id_poprire, id_admin, suma=None, motiv=None):
            self.primit = {
                "id_poprire": id_poprire, "id_admin": id_admin, "suma": suma, "motiv": motiv
            }
            return _rand_poprire(suma_incasata=0.0, status="activa")

    fals = _DepozitStorno()
    monkeypatch.setattr(rute_admin, "AdminRepository", lambda _client: fals)

    raspuns = await rute_admin.storneaza_poprire(
        ID_POPRIRE,
        StorneazaPoprireRequest(motiv="Incasare gresita"),
        administrator=_UserContextFals(user_id=ID_ADMIN),
        client=object(),
    )

    assert fals.primit["suma"] is None
    assert fals.primit["motiv"] == "Incasare gresita"
    assert fals.primit["id_admin"] == ID_ADMIN
    # O poprire stinsa care primeste banii inapoi redevine activa.
    assert raspuns.status == "activa"
    assert raspuns.suma_incasata == "0.00"


@pytest.mark.parametrize(
    ("cod", "stare"),
    [("NIMIC_DE_STORNAT", 409), ("PESTE_SUMA_INCASATA", 400), ("FARA_CONT_DESCHIS", 409)],
)
async def test_refuzurile_stornarii_nu_ies_500(monkeypatch, cod: str, stare: int) -> None:
    class _DepozitStorno(_DepozitFals):
        async def storneaza_incasarea(self, id_poprire, id_admin, suma=None, motiv=None):
            raise _EroareRpcFalsa(cod)

    monkeypatch.setattr(rute_admin, "AdminRepository", lambda _client: _DepozitStorno())

    with pytest.raises(HTTPException) as exc:
        await rute_admin.storneaza_poprire(
            ID_POPRIRE,
            StorneazaPoprireRequest(),
            administrator=_UserContextFals(user_id=ID_ADMIN),
            client=object(),
        )

    assert exc.value.status_code == stare
