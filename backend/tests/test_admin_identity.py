"""Revizuirea manuala a verificarilor: cine intra, ce vede, ce poate schimba."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    UserContext,
    get_current_user,
    get_user_supabase,
)
from app.main import app
from app.repositories import identity_repository as depozit
from app.services import admin_identity_service as serviciu

ADMIN = UserContext(user_id=uuid4(), access_token="token-de-test")
ID_CAZ = "2e28724e-596d-4656-b484-60b979587f80"
ID_USER = "5f801e91-0fd4-462f-a78c-61ec1d6dc12b"


def _caz(**suprascrieri) -> dict:
    baza = {
        "id": ID_CAZ,
        "id_user": ID_USER,
        "buletin_image_path": f"{ID_USER}/buletin.jpg",
        "selfie_image_path": f"{ID_USER}/selfie.jpg",
        "extracted_cnp": "5030805132808",
        "similarity_score": 0.36673,
        "threshold_folosit": 0.68,
        "status": "pending_review",
        "reviewed_by": None,
        "reviewed_at": None,
        "notes": None,
        "creat_la": "2026-08-19T10:00:00+00:00",
    }
    baza.update(suprascrieri)
    return baza


def _profil(**suprascrieri) -> dict:
    baza = {
        "id": ID_USER,
        "nume": "Ciuraru Costin",
        "email": "costin@exemplu.ro",
        "cnp": "5030805132808",
        "verification_status": "pending_review",
    }
    baza.update(suprascrieri)
    return baza


class _ClientRol:
    """Raspunde doar la interogarea de rol din cere_administrator.

    Rolul se citeste din user_roles.role, cu valoarea 'admin' (vezi ROL_ADMIN
    si migratia 0018). `rol=None` = niciun rand, cazul unui client obisnuit.
    """

    def __init__(self, rol: str | None = "admin") -> None:
        self._rol = rol

    def table(self, _nume: str):
        return self

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        class R:
            data = {"role": self._rol} if self._rol else None

        return R()


@pytest.fixture
def ca_admin():
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_user_supabase] = lambda: _ClientRol("admin")
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def depozit_fals(monkeypatch):
    """Inlocuieste accesul la baza de date; testele nu ating Supabase."""
    jurnal: dict = {"acces": [], "decizii": []}

    monkeypatch.setattr(depozit, "listeaza_dupa_status", lambda s, limita=100: [_caz()])
    monkeypatch.setattr(depozit, "obtine_caz", lambda i: _caz() if i == ID_CAZ else None)
    monkeypatch.setattr(depozit, "profiluri", lambda ids: {ID_USER: _profil()})
    monkeypatch.setattr(depozit, "url_semnat", lambda b, c, secunde=300: f"https://semnat/{b}")
    monkeypatch.setattr(
        depozit,
        "scrie_acces",
        lambda a, act, u=None, d=None: jurnal["acces"].append({"actiune": act}),
    )

    def _decizie(id_verificare, status, reviewed_by, notes):
        jurnal["decizii"].append({"status": status, "by": reviewed_by, "notes": notes})
        return _caz(status=status, reviewed_by=reviewed_by, reviewed_at="2026-08-20T09:00:00+00:00")

    monkeypatch.setattr(depozit, "scrie_decizie", _decizie)
    return jurnal


# ---------------------------------------------------------------------------
# Bariera de acces
# ---------------------------------------------------------------------------


def test_fara_token_nu_se_intra() -> None:
    client = TestClient(app)

    assert client.get("/api/identity/admin/pending").status_code == 401
    assert client.get(f"/api/identity/admin/case/{ID_CAZ}").status_code == 401
    assert client.post("/api/identity/admin/review", json={}).status_code == 401


def test_un_utilizator_obisnuit_primeste_403(depozit_fals) -> None:
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_user_supabase] = lambda: _ClientRol(None)
    try:
        raspuns = TestClient(app).get("/api/identity/admin/pending")
    finally:
        app.dependency_overrides.clear()

    assert raspuns.status_code == 403


# ---------------------------------------------------------------------------
# Continut
# ---------------------------------------------------------------------------


def test_lista_arata_cazurile_de_revizuit(ca_admin, depozit_fals) -> None:
    raspuns = TestClient(app).get("/api/identity/admin/pending")

    assert raspuns.status_code == 200
    cazuri = raspuns.json()
    assert len(cazuri) == 1
    assert cazuri[0]["nume"] == "Ciuraru Costin"
    assert cazuri[0]["status"] == "pending_review"


def test_scorul_e_prezentat_ca_distanta(ca_admin, depozit_fals) -> None:
    """0.367 fata de pragul 0.68 inseamna potrivire BUNA: mai mic = mai asemanator.

    Daca ar fi prezentat ca "similaritate", un om ar citi 0.37 ca esec si ar
    respinge un cont valid.
    """
    caz = TestClient(app).get("/api/identity/admin/pending").json()[0]

    assert caz["distanta_fete"] == 0.36673
    assert caz["prag"] == 0.68
    assert caz["sub_prag"] is True


def test_cnp_ul_extras_se_compara_cu_cel_declarat(ca_admin, depozit_fals) -> None:
    caz = TestClient(app).get("/api/identity/admin/pending").json()[0]

    assert caz["cnp_extras"] == caz["cnp_declarat"]
    assert caz["cnp_se_potriveste"] is True


def test_cnp_necitit_nu_inseamna_nepotrivire(ca_admin, depozit_fals, monkeypatch) -> None:
    """None si False cer reactii diferite: "nu stim" nu e "nu se potriveste"."""
    monkeypatch.setattr(
        depozit, "listeaza_dupa_status", lambda s, limita=100: [_caz(extracted_cnp=None)]
    )

    caz = TestClient(app).get("/api/identity/admin/pending").json()[0]

    assert caz["cnp_se_potriveste"] is None


def test_pozele_vin_ca_url_semnat(ca_admin, depozit_fals) -> None:
    detaliu = TestClient(app).get(f"/api/identity/admin/case/{ID_CAZ}").json()

    assert detaliu["url_buletin"].startswith("https://semnat/buletine")
    assert detaliu["url_selfie"].startswith("https://semnat/selfie-uri")
    assert detaliu["secunde_valabilitate"] > 0


def test_un_caz_inexistent_da_404(ca_admin, depozit_fals) -> None:
    raspuns = TestClient(app).get(f"/api/identity/admin/case/{uuid4()}")

    assert raspuns.status_code == 404


# ---------------------------------------------------------------------------
# Decizia
# ---------------------------------------------------------------------------


def test_aprobarea_scrie_decizia_si_adminul(ca_admin, depozit_fals) -> None:
    raspuns = TestClient(app).post(
        "/api/identity/admin/review",
        json={"verification_id": ID_CAZ, "decizie": "verified", "note": "acte in regula"},
    )

    assert raspuns.status_code == 200
    assert raspuns.json()["status"] == "verified"
    assert depozit_fals["decizii"] == [
        {"status": "verified", "by": str(ADMIN.user_id), "notes": "acte in regula"}
    ]


def test_respingerea_merge_la_fel(ca_admin, depozit_fals) -> None:
    raspuns = TestClient(app).post(
        "/api/identity/admin/review",
        json={"verification_id": ID_CAZ, "decizie": "rejected"},
    )

    assert raspuns.status_code == 200
    assert raspuns.json()["status"] == "rejected"


def test_o_decizie_inventata_e_respinsa(ca_admin, depozit_fals) -> None:
    raspuns = TestClient(app).post(
        "/api/identity/admin/review",
        json={"verification_id": ID_CAZ, "decizie": "pending_review"},
    )

    assert raspuns.status_code == 422


def test_decizia_pe_un_caz_inexistent_da_404(ca_admin, depozit_fals) -> None:
    raspuns = TestClient(app).post(
        "/api/identity/admin/review",
        json={"verification_id": str(uuid4()), "decizie": "verified"},
    )

    assert raspuns.status_code == 404


def test_fiecare_citire_lasa_o_urma(ca_admin, depozit_fals) -> None:
    """Dreptul de a vedea buletinul cuiva vine cu urma ca l-ai folosit."""
    client = TestClient(app)
    client.get("/api/identity/admin/pending")
    client.get(f"/api/identity/admin/case/{ID_CAZ}")
    client.post(
        "/api/identity/admin/review",
        json={"verification_id": ID_CAZ, "decizie": "verified"},
    )

    assert [u["actiune"] for u in depozit_fals["acces"]] == [
        "lista_verificari",
        "vede_verificare",
        "decide_verificare",
    ]
