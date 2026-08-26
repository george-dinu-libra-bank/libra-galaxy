from fastapi.testclient import TestClient

from app.main import app

CLIENT = TestClient(app)


def test_cheltuieli_pe_categorie_cere_autentificare() -> None:
    assert CLIENT.get("/api/v1/analiza/cheltuieli-pe-categorie").status_code == 401


def test_cashflow_cere_autentificare() -> None:
    assert CLIENT.get("/api/v1/analiza/cashflow").status_code == 401


def test_tranzactii_categorizate_cere_autentificare() -> None:
    assert CLIENT.get("/api/v1/analiza/tranzactii-categorizate").status_code == 401


def test_categorii_manuale_cere_autentificare() -> None:
    assert CLIENT.post(
        "/api/v1/analiza/categorii-manuale", json={"id_tranzactie": "abc", "categorie": "restaurant"}
    ).status_code == 401
