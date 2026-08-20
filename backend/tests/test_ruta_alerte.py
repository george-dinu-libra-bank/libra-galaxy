"""Lantul complet al rutei /alerte: HTTP -> serviciu -> detector -> raspuns.

Testele de aici nu ating Supabase: clientul e inlocuit cu unul fals care intoarce
randuri pregatite, in aceeasi forma ca tabela tranzactii.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.config import Settings, get_settings
from app.main import app

UTILIZATOR = UserContext(user_id=uuid4(), access_token="token-de-test")
ACUM = datetime.now(timezone.utc)


class _Raspuns:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _Interogare:
    """Imita lantul fluent al supabase-py: totul intoarce self, execute() da datele."""

    def __init__(self, randuri: list[dict]) -> None:
        self._randuri = randuri

    def select(self, *_a, **_k) -> "_Interogare":
        return self

    def or_(self, *_a, **_k) -> "_Interogare":
        return self

    def eq(self, *_a, **_k) -> "_Interogare":
        return self

    def gte(self, *_a, **_k) -> "_Interogare":
        return self

    def lte(self, *_a, **_k) -> "_Interogare":
        return self

    def order(self, *_a, **_k) -> "_Interogare":
        return self

    def limit(self, *_a, **_k) -> "_Interogare":
        return self

    def execute(self) -> _Raspuns:
        return _Raspuns(self._randuri)


class _ClientFals:
    def __init__(self, tranzactii: list[dict]) -> None:
        self._tranzactii = tranzactii

    def table(self, nume: str) -> _Interogare:
        return _Interogare(self._tranzactii if nume == "tranzactii" else [])


def _plata(zile_in_urma: float, suma: float, descriere: str) -> dict:
    return {
        "id": str(uuid4()),
        "suma": suma,
        "valuta": "RON",
        "descriere": descriere,
        "creat_la": (ACUM - timedelta(days=zile_in_urma)).isoformat(),
        "id_user_send": str(UTILIZATOR.user_id),
        "id_user_recieve": None,
    }


def _cu_tranzactii(randuri: list[dict]) -> None:
    app.dependency_overrides[get_current_user] = lambda: UTILIZATOR
    app.dependency_overrides[get_user_supabase] = lambda: _ClientFals(randuri)
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="http://supabase.invalid",
        supabase_anon_key="test-anon-key",
    )


def _cere(randuri: list[dict]):
    _cu_tranzactii(randuri)
    try:
        return TestClient(app).get("/api/v1/alerte?zile=180")
    finally:
        app.dependency_overrides.clear()


def test_ruta_intoarce_constatarile_detectorului() -> None:
    randuri = [_plata(60 - i * 5, 42.0 + i, "Kaufland ref 1234567") for i in range(8)]
    randuri.append(_plata(2, 2450.0, "Kaufland ref 7654321"))

    raspuns = _cere(randuri)

    assert raspuns.status_code == 200
    constatari = raspuns.json()
    assert [c["tip"] for c in constatari] == ["suma_neobisnuita"]
    assert constatari[0]["suma"] == 2450.0
    assert constatari[0]["scor"] > 0


def test_platile_obisnuite_dau_lista_goala() -> None:
    randuri = [_plata(60 - i * 5, 40.0 + (i % 3), "Kaufland ref 1234567") for i in range(10)]

    raspuns = _cere(randuri)

    assert raspuns.status_code == 200
    assert raspuns.json() == []


def test_raspunsul_are_forma_din_schema() -> None:
    randuri = [_plata(60 - i * 5, 100.0, "Kaufland ref 1234567") for i in range(8)]
    randuri.append(_plata(1, 4200.0, "Bijuterii Lux ref 9111234"))

    constatari = _cere(randuri).json()

    assert constatari
    assert set(constatari[0]) == {
        "id_tranzactie",
        "data",
        "suma",
        "valuta",
        "comerciant",
        "tip",
        "explicatie",
        "scor",
    }


def test_perioada_ceruta_e_marginita() -> None:
    _cu_tranzactii([])
    try:
        client = TestClient(app)
        assert client.get("/api/v1/alerte?zile=400").status_code == 422
        assert client.get("/api/v1/alerte?zile=0").status_code == 422
    finally:
        app.dependency_overrides.clear()
