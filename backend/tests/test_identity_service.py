import pytest

from app.infrastructure.ocr import extrage_cnp
from app.repositories import identity_repository
from app.services import identity_service

CNP_VALID = "1970101221144"
ID_USER = "5f801e91-0fd4-462f-a78c-61ec1d6dc12b"


# ---------------------------------------------------------------------------
# Citirea CNP-ului: Azure intai, Tesseract ca rezerva
# ---------------------------------------------------------------------------


class _SetariCuChei:
    document_intelligence_configured = True


class _FaraChei:
    document_intelligence_configured = False


def _azure_care_intoarce(citit):
    class _Azure:
        def __init__(self, *a, **k) -> None:
            pass

        async def citeste(self, *a, **k):
            return citit

    return _Azure


async def test_cnp_din_cuvintele_azure_pastreaza_increderea_reala(monkeypatch):
    """Diferenta care conteaza fata de Tesseract.

    Acolo increderea era „cate din cele opt incercari au cazut de acord" — o
    masura a stabilitatii motorului, nu a lizibilitatii buletinului. Azure
    raporteaza incredere pe cuvant, deci se poate spune cat de clar s-au citit
    chiar cifrele CNP-ului.
    """
    from app.providers.document_intelligence import Cuvant, TextCitit

    citit = TextCitit(
        text=f"CNP {CNP_VALID}",
        cuvinte=(Cuvant("CNP", 0.99), Cuvant(CNP_VALID, 0.93)),
    )
    monkeypatch.setattr(identity_service, "get_settings", lambda: _SetariCuChei())
    monkeypatch.setattr(identity_service, "AzureDocumentIntelligence", _azure_care_intoarce(citit))
    monkeypatch.setattr(
        identity_service, "extrage_cnp", lambda *a: pytest.fail("nu trebuia sa se cheme Tesseract")
    )

    cnp, incredere = await identity_service.extrage_cnp_din_buletin(b"poza", "image/jpeg")

    assert cnp == CNP_VALID
    assert incredere == pytest.approx(0.93)


async def test_cnp_lipit_de_alt_text_se_cauta_in_pagina(monkeypatch):
    """Cand CNP-ul nu e un cuvant intreg, textul e tot bun — nu se mai plateste
    un tur de Tesseract pe aceeasi poza."""
    from app.providers.document_intelligence import Cuvant, TextCitit

    citit = TextCitit(
        text=f"SERIA RR NR 849201\nCNP/PERSONAL NO {CNP_VALID} SEX M",
        cuvinte=(Cuvant("SERIA", 0.80), Cuvant("RR", 0.60)),
    )
    monkeypatch.setattr(identity_service, "get_settings", lambda: _SetariCuChei())
    monkeypatch.setattr(identity_service, "AzureDocumentIntelligence", _azure_care_intoarce(citit))
    monkeypatch.setattr(
        identity_service, "extrage_cnp", lambda *a: pytest.fail("nu trebuia sa se cheme Tesseract")
    )

    cnp, incredere = await identity_service.extrage_cnp_din_buletin(b"poza", "image/jpeg")

    assert cnp == CNP_VALID
    # Fara un cuvant caruia sa-i atribuim cifrele, ramane increderea paginii.
    assert incredere == pytest.approx(0.70)


async def test_azure_picat_cade_pe_tesseract(monkeypatch):
    from app.core.errors import AiProviderUnavailableError

    class _AzureCazut:
        def __init__(self, *a, **k) -> None:
            pass

        async def citeste(self, *a, **k):
            raise AiProviderUnavailableError("pana")

    monkeypatch.setattr(identity_service, "get_settings", lambda: _SetariCuChei())
    monkeypatch.setattr(identity_service, "AzureDocumentIntelligence", _AzureCazut)
    monkeypatch.setattr(identity_service, "extrage_cnp", lambda *a: (CNP_VALID, 0.5))

    assert await identity_service.extrage_cnp_din_buletin(b"poza") == (CNP_VALID, 0.5)


async def test_fara_chei_merge_direct_pe_tesseract(monkeypatch):
    monkeypatch.setattr(identity_service, "get_settings", lambda: _FaraChei())
    monkeypatch.setattr(identity_service, "extrage_cnp", lambda *a: (CNP_VALID, 0.5))

    assert await identity_service.extrage_cnp_din_buletin(b"poza") == (CNP_VALID, 0.5)


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
