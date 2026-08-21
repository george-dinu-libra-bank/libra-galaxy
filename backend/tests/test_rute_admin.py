"""Zona administratorului: cine intra, cine nu, si ce iese.

Supabase e inlocuit cu un client fals; ce se verifica aici e bariera de acces si
forma raspunsurilor, nu politicile RLS — acelea traiesc in baza de date si se
verifica rulland 0004_rol_administrator.sql.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.config import Settings, get_settings
from app.main import app

ADMIN = UserContext(user_id=uuid4(), access_token="token-de-test")
ACUM = datetime.now(timezone.utc)


class _Raspuns:
    def __init__(self, data) -> None:
        self.data = data


class _Interogare:
    """Lantul fluent al supabase-py: totul intoarce self, execute() da datele.

    `maybe_single()` schimba forma raspunsului dintr-o lista intr-un singur
    rand, exact ca la clientul adevarat.
    """

    def __init__(self, randuri: list[dict]) -> None:
        self._randuri = randuri
        self._unul = False

    def __getattr__(self, _nume):
        def oricare(*_a, **_k):
            return self

        return oricare

    def maybe_single(self):
        self._unul = True
        return self

    def execute(self) -> _Raspuns:
        if self._unul:
            return _Raspuns(self._randuri[0] if self._randuri else None)
        return _Raspuns(self._randuri)


class _Urma(_Interogare):
    def __init__(self, jurnal: list[dict]) -> None:
        super().__init__([])
        self._jurnal = jurnal

    def insert(self, rand: dict):
        self._jurnal.append(rand)
        return self


class _ClientFals:
    def __init__(self, rol: str = "admin", tranzactii: list[dict] | None = None) -> None:
        self._rol = rol
        self._tranzactii = tranzactii or []
        self.inserari: list[dict] = []

    def table(self, nume: str):
        # Rolul se citeste din user_roles, nu din profiles.rol: coloana aceea nu
        # exista in proiectul real (migrarea 0008 din repo n-a fost aplicata),
        # iar `cere_administrator` a fost consolidat pe user_roles.
        if nume == "user_roles":
            return _Interogare([{"user_id": str(ADMIN.user_id), "role": self._rol}])
        if nume == "profiles":
            return _Interogare(
                [
                    {
                        "id": str(ADMIN.user_id),
                        "nume": "Ana Popescu",
                        "email": "ana@exemplu.ro",
                        "telefon": "+40712345678",
                        "iban_cont": "RO49LIBR1B310075938400",
                        "creat_la": "2026-01-15T09:00:00+00:00",
                    }
                ]
            )
        if nume == "tranzactii":
            return _Interogare(self._tranzactii)
        if nume == "acces_administrator":
            return _Urma(self.inserari)
        return _Interogare([])


def _plata(zile_in_urma: float, suma: float, descriere: str) -> dict:
    return {
        "id": str(uuid4()),
        "suma": suma,
        "valuta": "RON",
        "descriere": descriere,
        "creat_la": (ACUM - timedelta(days=zile_in_urma)).isoformat(),
        "id_user_send": str(ADMIN.user_id),
        "id_user_recieve": None,
    }


def _cu_client(client: _ClientFals) -> None:
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_user_supabase] = lambda: client
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="http://supabase.invalid", supabase_anon_key="test-anon-key"
    )


def test_zona_de_administrator_cere_autentificare() -> None:
    client = TestClient(app)

    assert client.get("/api/v1/admin/conturi-semnalate").status_code == 401
    assert client.get(f"/api/v1/admin/raport/{uuid4()}").status_code == 401
    assert client.get(f"/api/v1/admin/raport/{uuid4()}/pdf").status_code == 401


def test_un_client_obisnuit_primeste_403() -> None:
    _cu_client(_ClientFals(rol="client"))
    try:
        raspuns = TestClient(app).get("/api/v1/admin/conturi-semnalate")
    finally:
        app.dependency_overrides.clear()

    assert raspuns.status_code == 403


def test_administratorul_primeste_lista() -> None:
    randuri = [_plata(60 - i * 5, 42.0 + i, "Kaufland ref 1234567") for i in range(8)]
    randuri.append(_plata(2, 2450.0, "Kaufland ref 7654321"))
    _cu_client(_ClientFals(tranzactii=randuri))
    try:
        raspuns = TestClient(app).get("/api/v1/admin/conturi-semnalate?zile=180")
    finally:
        app.dependency_overrides.clear()

    assert raspuns.status_code == 200
    conturi = raspuns.json()
    assert conturi
    assert conturi[0]["numar_semnalari"] >= 1
    assert "suma_neobisnuita" in conturi[0]["tipuri"]


def test_raportul_pdf_se_descarca() -> None:
    randuri = [_plata(60 - i * 5, 42.0 + i, "Kaufland ref 1234567") for i in range(8)]
    randuri.append(_plata(2, 2450.0, "Kaufland ref 7654321"))
    _cu_client(_ClientFals(tranzactii=randuri))
    try:
        raspuns = TestClient(app).get(
            f"/api/v1/admin/raport/{ADMIN.user_id}/pdf?zile=180&sinteza=false"
        )
    finally:
        app.dependency_overrides.clear()

    assert raspuns.status_code == 200
    assert raspuns.headers["content-type"] == "application/pdf"
    assert "attachment" in raspuns.headers["content-disposition"]
    assert raspuns.content.startswith(b"%PDF-")


def test_raportul_csv_se_descarca() -> None:
    randuri = [_plata(60 - i * 5, 42.0 + i, "Kaufland ref 1234567") for i in range(8)]
    randuri.append(_plata(2, 2450.0, "Kaufland ref 7654321"))
    _cu_client(_ClientFals(tranzactii=randuri))
    try:
        raspuns = TestClient(app).get(f"/api/v1/admin/raport/{ADMIN.user_id}/csv?zile=180")
    finally:
        app.dependency_overrides.clear()

    assert raspuns.status_code == 200
    assert raspuns.headers["content-type"].startswith("text/csv")
    assert "suma_neobisnuita" in raspuns.text


def test_fiecare_citire_lasa_o_urma() -> None:
    """Dreptul de a citi datele altcuiva vine cu urma ca l-ai folosit."""
    client = _ClientFals(tranzactii=[_plata(1, 100.0, "Kaufland ref 1")])
    _cu_client(client)
    try:
        TestClient(app).get(f"/api/v1/admin/raport/{ADMIN.user_id}/csv?zile=30")
    finally:
        app.dependency_overrides.clear()

    assert len(client.inserari) == 1
    assert client.inserari[0]["actiune"] == "raport_csv"
    assert client.inserari[0]["id_administrator"] == str(ADMIN.user_id)


def test_perioada_ceruta_e_marginita() -> None:
    _cu_client(_ClientFals())
    try:
        client = TestClient(app)
        assert client.get("/api/v1/admin/conturi-semnalate?zile=400").status_code == 422
        assert client.get(f"/api/v1/admin/raport/{uuid4()}?zile=0").status_code == 422
    finally:
        app.dependency_overrides.clear()
