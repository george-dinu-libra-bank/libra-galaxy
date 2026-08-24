import pytest

from app.infrastructure.ocr import extrage_cnp
from app.repositories import identity_repository
from app.services import identity_service

CNP_VALID = "1970101221144"
ID_USER = "5f801e91-0fd4-462f-a78c-61ec1d6dc12b"


def test_extrage_cnp_din_text_fara_potriviri():
    # Bytes invalizi ca imagine -> nu trebuie sa arunce exceptie.
    cnp, incredere = extrage_cnp(b"nu-e-o-imagine")
    assert cnp is None
    assert incredere == 0.0


# ---------------------------------------------------------------------------
# Login biometric: oprirea din setari
# ---------------------------------------------------------------------------


@pytest.fixture
def fara_deepface(monkeypatch):
    """
    Prinde orice apel la comparatia fetelor. Testele de mai jos verifica exact
    ca NU se ajunge pana acolo — DeepFace e si scump, si irelevant cand
    raspunsul e deja 'nu'.
    """
    apeluri = []
    monkeypatch.setattr(
        identity_service,
        "verifica_fete",
        lambda *a, **k: apeluri.append(a) or pytest.fail("nu trebuia sa se compare fetele"),
    )
    return apeluri


def test_biometria_oprita_refuza_loginul(monkeypatch, fara_deepface):
    monkeypatch.setattr(
        identity_repository, "gaseste_user_dupa_email", lambda e: (ID_USER, False)
    )
    # Selfie-ul verificat exista — deci singurul motiv de refuz e comutatorul.
    monkeypatch.setattr(
        identity_repository, "gaseste_selfie_verificat", lambda i: f"{ID_USER}/selfie.jpg"
    )

    assert identity_service.verifica_login_fata("costin@exemplu.ro", b"poza") is False


def test_contul_inexistent_refuza_la_fel(monkeypatch, fara_deepface):
    """
    Acelasi False si aceeasi tacere ca la biometria oprita: din raspuns nu
    trebuie sa se poata deduce care din cele doua e cazul.
    """
    monkeypatch.setattr(
        identity_repository, "gaseste_user_dupa_email", lambda e: (None, False)
    )

    assert identity_service.verifica_login_fata("nimeni@exemplu.ro", b"poza") is False


def test_biometria_activata_ajunge_la_comparatie(monkeypatch):
    monkeypatch.setattr(
        identity_repository, "gaseste_user_dupa_email", lambda e: (ID_USER, True)
    )
    monkeypatch.setattr(
        identity_repository, "gaseste_selfie_verificat", lambda i: f"{ID_USER}/selfie.jpg"
    )
    monkeypatch.setattr(identity_repository, "descarca_imagine", lambda b, c: b"referinta")

    class _Rezultat:
        verified = True

    monkeypatch.setattr(identity_service, "verifica_fete", lambda *a: _Rezultat())

    assert identity_service.verifica_login_fata("costin@exemplu.ro", b"poza") is True
