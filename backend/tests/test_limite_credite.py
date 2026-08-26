"""Gardurile de pe rutele de creditare: limita de rata si poarta de demo.

`credite.py` era singurul router fara nicio limita, desi are cele mai scumpe
rute din aplicatie — `documente` cheama Azure Document Intelligence (bani
reali, per pagina) si `evalueaza` cheama un LLM. Cat OCR-ul era local si gratis
lipsa nu se vedea; de ieri se vede.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    UserContext,
    cere_administrator,
    get_credit_service,
    get_current_user,
)
from app.api.routes import credite as rute_credite
from app.main import app
from app.services.credit_service import CreditService
from tests.test_flux_credit import ID_USER, DepozitFals, _cerere


@pytest.fixture
def client():
    depozit = DepozitFals()
    utilizator = UserContext(user_id=ID_USER, access_token="test")
    app.dependency_overrides[get_current_user] = lambda: utilizator
    app.dependency_overrides[cere_administrator] = lambda: utilizator
    app.dependency_overrides[get_credit_service] = lambda: CreditService(depozit)
    yield TestClient(app), depozit
    app.dependency_overrides.clear()


def _pdf() -> bytes:
    from reportlab.pdfgen import canvas

    memorie = io.BytesIO()
    pagina = canvas.Canvas(memorie)
    pagina.drawString(60, 780, "Salariul net lunar: 4.850,00 lei")
    pagina.showPage()
    pagina.save()
    return memorie.getvalue()


def test_a_unsprezecea_incarcare_primeste_429_nu_500(client) -> None:
    """Zece adeverinte in cinci minute inseamna deja altceva decat o cerere de
    credit. A unsprezecea trebuie refuzata curat, cu 429."""
    c, _ = client
    id_cerere = _cerere(c)

    coduri = [
        c.post(
            f"/api/v1/credite/cereri/{id_cerere}/documente",
            files={"fisier": ("a.pdf", _pdf(), "application/pdf")},
        ).status_code
        for _ in range(11)
    ]

    assert coduri[-1] == 429
    assert 429 not in coduri[:10]


def test_limita_e_pe_utilizator_nu_globala(client) -> None:
    """Un utilizator care si-a consumat limita nu trebuie sa-i blocheze pe
    ceilalti — de-aia cheia contine user_id."""
    c, _ = client
    id_cerere = _cerere(c)

    for _ in range(11):
        c.post(
            f"/api/v1/credite/cereri/{id_cerere}/documente",
            files={"fisier": ("a.pdf", _pdf(), "application/pdf")},
        )

    altcineva = UserContext(user_id="9f2c1e40-0000-4000-8000-000000000001", access_token="test")
    app.dependency_overrides[get_current_user] = lambda: altcineva

    raspuns = c.post(
        f"/api/v1/credite/cereri/{id_cerere}/documente",
        files={"fisier": ("a.pdf", _pdf(), "application/pdf")},
    )

    assert raspuns.status_code != 429


# ---------------------------------------------------------------------------
# Poarta de demo pe avanseaza-timp
# ---------------------------------------------------------------------------


def test_avanseaza_timp_refuzat_in_afara_mediilor_de_demo(client, monkeypatch) -> None:
    """Ruta muta "azi"-ul cu pana la 120 de luni si chiar incaseaza scadentele —
    acelasi RPC ca procesarea obisnuita. Statea pe router-ul normal, cu doar o
    sesiune valida in fata."""
    c, _ = client

    class _Setari:
        environment = "production"

    monkeypatch.setattr(rute_credite, "get_settings", lambda: _Setari())

    raspuns = c.post("/api/v1/credite/00000000-0000-4000-8000-000000000001/avanseaza-timp?luni=120")

    assert raspuns.status_code == 403


def test_mediile_de_demo_raman_deschise(client, monkeypatch) -> None:
    """Poarta nu trebuie sa strice demonstratia — se verifica pe cod de eroare,
    nu pe succes: creditul din test nu exista, deci raspunsul corect e 404, iar
    ce conteaza e ca NU e 403."""
    c, _ = client

    class _Setari:
        environment = "local"

    monkeypatch.setattr(rute_credite, "get_settings", lambda: _Setari())

    raspuns = c.post("/api/v1/credite/00000000-0000-4000-8000-000000000001/avanseaza-timp?luni=1")

    assert raspuns.status_code != 403


def test_lista_alba_nu_negatie() -> None:
    """Un mediu nou, nebotezat, trebuie sa porneasca INCHIS.

    Cu `!= "production"` ar fi pornit deschis, iar greseala s-ar fi vazut abia
    cand cineva avanseaza timpul intr-un mediu real.
    """
    assert "production" not in rute_credite.MEDII_CU_DEMO
    assert "staging" not in rute_credite.MEDII_CU_DEMO
    assert "local" in rute_credite.MEDII_CU_DEMO
