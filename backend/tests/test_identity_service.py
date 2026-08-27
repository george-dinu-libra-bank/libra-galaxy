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


# ---------------------------------------------------------------------------
# Alegerea CNP-ului dintre mai multi candidati
# ---------------------------------------------------------------------------

from app.infrastructure.ocr import _candidati_din_text, cifra_control_valida


def test_cifra_de_control():
    assert cifra_control_valida("5030805132808") is True
    assert cifra_control_valida("5030805132809") is False
    assert cifra_control_valida("123") is False
    assert cifra_control_valida("abcdefghijklm") is False


def test_banda_mrz_nu_trece_drept_zona_vizuala():
    """
    Randul de jos de pe un buletin vechi, asa cum il vede Tesseract cu
    whitelist doar pe cifre: MX6419944ROU6409029M7709025222034296.
    Are 30 de cifre, deci e MRZ, nu campul CNP.
    """
    text = "1640902220342\n64199446409029770902522203429"

    candidati = _candidati_din_text(text)
    dupa_cnp = {cnp: vizuala for cnp, vizuala in candidati}

    assert dupa_cnp["1640902220342"] is True
    # Tot ce s-a extras din randul lung e marcat ca venind din MRZ.
    assert any(not vizuala for _, vizuala in candidati)


def test_randul_scurt_ramane_zona_vizuala():
    candidati = _candidati_din_text("CNP 5030805132808")

    assert candidati == [("5030805132808", True)]


def test_cnp_ul_din_zona_vizuala_bate_mrz_ul_mai_frecvent(monkeypatch):
    """
    Cazul buletinelor vechi: banda MRZ produce constant un sir de 13 cifre,
    mai des decat e citit campul CNP. Inainte castiga MRZ-ul, pentru ca
    alegerea se facea doar pe frecventa.

    CNP-ul de pe buletinul din exemplu (un model fals) n-are nici el cifra de
    control valida, deci diferenta o face strict zona din care provine.
    """
    from app.infrastructure import ocr

    def fals(imagine, config=""):
        # Randul de jos (MRZ, 30+ cifre) apare la fiecare incercare; campul CNP
        # se citeste mai greu, dar e pe un rand scurt.
        return "1640902220342\n64199446409029770902522203429\n64199446409029770902522203429"

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", fals)
    monkeypatch.setattr(ocr, "_variante_preprocesare", lambda img: [img])
    monkeypatch.setattr(ocr.Image, "open", lambda b: _ImagineFalsa())

    cnp, _ = ocr.extrage_cnp(b"oricare")

    assert cnp == "1640902220342"


class _ImagineFalsa:
    size = (1200, 800)
    width, height = 1200, 800

    def load(self):
        return None


def test_cifra_de_control_departajeaza_in_zona_vizuala(monkeypatch):
    """
    Doua citiri ale aceluiasi camp, una gresita. Amandoua din zona vizuala,
    deci decide cifra de control — chiar daca cea gresita apare mai des.
    """
    from app.infrastructure import ocr

    monkeypatch.setattr(
        ocr.pytesseract, "image_to_string",
        lambda imagine, config="": "5030805132809\n5030805132809\n5030805132808",
    )
    monkeypatch.setattr(ocr, "_variante_preprocesare", lambda img: [img])
    monkeypatch.setattr(ocr.Image, "open", lambda b: _ImagineFalsa())

    cnp, _ = ocr.extrage_cnp(b"oricare")

    assert cnp == "5030805132808"


def test_eticheta_cnp_bate_toate_capcanele_de_pe_buletin(monkeypatch):
    """
    Cazul din poza reala, cu toate sursele de fals pozitiv de pe un buletin
    vechi: banda MRZ, datele de valabilitate lipite si numarul documentului.
    Toate au castigat, pe rand, in fata CNP-ului adevarat.
    """
    from app.infrastructure import ocr

    CU_LITERE = (
        "ROUMANIE ROMANIA\n"
        "CNP 1640902220342 SERIA MX NR 641994\n"
        "WICK JOHN\n"
        "Valabilitate 06.01.17-02.09.2077\n"
        "MX6419944ROU6409029M7709025222034296\n"
    )
    # Trecerea cu whitelist vede doar cifre, deci pierde eticheta.
    DOAR_CIFRE = (
        "1640902220342641994\n"
        "06011702092077\n"
        "64199446409029770902522203429\n"
        "06011702092077\n"
    )

    def ocr_fals(imagine, lang=None, config=""):
        return CU_LITERE if "whitelist" not in config else DOAR_CIFRE

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", ocr_fals)
    monkeypatch.setattr(ocr, "_variante_preprocesare", lambda img: [img])
    monkeypatch.setattr(ocr.Image, "open", lambda b: _ImagineFalsa())

    cnp, _ = ocr.extrage_cnp(b"oricare")

    assert cnp == "1640902220342"
