"""
Teste pentru feedback-ul de calitate a pozei.

Imaginile se sintetizeaza cu numpy, nu se citesc de pe disc: un fixture .jpg
n-ar spune nimanui de ce e "prea intunecat", pe cand `np.zeros(...)` spune
exact. Detectia fetelor se monkeypatch-uieste — DeepFace ruleaza doar in
container (trage TensorFlow), iar restul suitei se bazeaza pe acelasi lucru.
"""

import io

import numpy as np
import pytest
from PIL import Image

from app.infrastructure import calitate_poza


def _poza(arr: np.ndarray) -> bytes:
    tampon = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8)).save(tampon, format="PNG")
    return tampon.getvalue()


def _uniforma(valoare: int, latura: int = 512) -> bytes:
    return _poza(np.full((latura, latura, 3), valoare, dtype=np.uint8))


def _zgomot(latura: int = 512, seed: int = 7) -> bytes:
    """Poza bine expusa si clara: zgomot in jurul lui 128, deci si contrast, si detalii."""
    generator = np.random.default_rng(seed)
    return _poza(np.clip(generator.normal(128, 40, (latura, latura, 3)), 0, 255))


def _fata(x=150, y=150, w=220, h=220, confidence=0.95) -> dict:
    return {"facial_area": {"x": x, "y": y, "w": w, "h": h}, "confidence": confidence}


@pytest.fixture
def fara_detector(monkeypatch):
    """Detectorul intoarce None = 'n-am putut rula' — izoleaza verificarile de expunere."""
    monkeypatch.setattr(calitate_poza, "_detecteaza_fete", lambda arr: None)


def coduri(raport) -> list[str]:
    return [problema.cod for problema in raport.probleme]


# --- Expunere ---------------------------------------------------------------


def test_poza_neagra_e_prea_intunecata(fara_detector):
    raport = calitate_poza.analizeaza_selfie(_uniforma(0))

    assert not raport.acceptabila
    assert "prea_intunecata" in coduri(raport)
    assert any(p.blocanta for p in raport.probleme)


def test_poza_alba_e_prea_luminoasa(fara_detector):
    raport = calitate_poza.analizeaza_selfie(_uniforma(255))

    assert not raport.acceptabila
    assert "prea_luminoasa" in coduri(raport)


def test_gri_uniform_e_neclar_si_sters(fara_detector):
    """Expunerea e in regula, dar nu exista nici detalii, nici contrast."""
    raport = calitate_poza.analizeaza_selfie(_uniforma(128))

    assert "neclara" in coduri(raport)
    assert "contrast_slab" in coduri(raport)
    assert not raport.acceptabila  # 'neclara' e blocanta, 'contrast_slab' nu


def test_pe_poza_stricata_de_expunere_nu_se_mai_reclama_blurul(fara_detector):
    """
    Un dreptunghi negru are varianta zero, deci ar iesi si 'neclara', si
    'contrast_slab'. Omul trebuie sa primeasca un singur mesaj, cel adevarat.
    """
    raport = calitate_poza.analizeaza_selfie(_uniforma(0))

    assert "neclara" not in coduri(raport)
    assert "contrast_slab" not in coduri(raport)


# --- Detectia fetei ---------------------------------------------------------


def test_nicio_fata_detectata(monkeypatch):
    monkeypatch.setattr(calitate_poza, "_detecteaza_fete", lambda arr: [])
    raport = calitate_poza.analizeaza_selfie(_zgomot())

    assert not raport.acceptabila
    assert "fara_fata" in coduri(raport)


def test_o_singura_fata_bine_expusa_trece(monkeypatch):
    monkeypatch.setattr(calitate_poza, "_detecteaza_fete", lambda arr: [_fata()])
    raport = calitate_poza.analizeaza_selfie(_zgomot())

    assert raport.acceptabila
    assert coduri(raport) == []


def test_mai_multe_fete(monkeypatch):
    monkeypatch.setattr(
        calitate_poza, "_detecteaza_fete", lambda arr: [_fata(), _fata(x=10, y=10, w=80, h=80)]
    )
    raport = calitate_poza.analizeaza_selfie(_zgomot())

    assert not raport.acceptabila
    assert "mai_multe_fete" in coduri(raport)


def test_fata_prea_mica(monkeypatch):
    # 60x60 din 512x512 = ~1.4% din cadru, sub pragul de 8%.
    monkeypatch.setattr(calitate_poza, "_detecteaza_fete", lambda arr: [_fata(w=60, h=60)])
    raport = calitate_poza.analizeaza_selfie(_zgomot())

    assert "fata_prea_mica" in coduri(raport)


def test_detector_indisponibil_nu_raporteaza_fara_fata(fara_detector):
    """
    None inseamna 'nu stim', nu 'nu e nicio fata' — o picare a TensorFlow
    n-are voie sa-i spuna omului ca nu i se vede fata.
    """
    raport = calitate_poza.analizeaza_selfie(_zgomot())

    assert "fara_fata" not in coduri(raport)
    assert raport.acceptabila


def test_expunerea_se_masoara_pe_fata_nu_pe_toata_poza(monkeypatch):
    """
    Contrejour: fata in umbra pe un fundal de fereastra. Media pe toata poza e
    rezonabila, dar ArcFace n-are ce compara — trebuie sa pice.
    """
    arr = np.full((512, 512, 3), 250, dtype=np.uint8)
    arr[150:370, 150:370] = 5  # fata, aproape neagra

    monkeypatch.setattr(calitate_poza, "_detecteaza_fete", lambda a: [_fata()])
    raport = calitate_poza.analizeaza_selfie(_poza(arr))

    assert "prea_intunecata" in coduri(raport)


# --- Ordinea mesajelor ------------------------------------------------------


def test_poza_neagra_raporteaza_intai_lumina_nu_lipsa_fetei(monkeypatch):
    """
    O poza neagra chiar n-are nicio fata detectabila, dar mesajul util e
    "aprinde lumina", nu "nu gasim nicio fata" — prima problema e cea afisata.
    """
    monkeypatch.setattr(calitate_poza, "_detecteaza_fete", lambda arr: [])
    raport = calitate_poza.analizeaza_selfie(_uniforma(0))

    assert coduri(raport)[0] == "prea_intunecata"
    assert "fara_fata" in coduri(raport)


# --- Buletin ----------------------------------------------------------------


def test_documentul_nu_cauta_fete(monkeypatch):
    apeluri = []
    monkeypatch.setattr(
        calitate_poza, "_detecteaza_fete", lambda arr: apeluri.append(arr) or []
    )

    calitate_poza.analizeaza_document(_zgomot(latura=1200))

    assert apeluri == []


def test_document_prea_mic(fara_detector):
    raport = calitate_poza.analizeaza_document(_zgomot(latura=400))

    assert "rezolutie_mica" in coduri(raport)
    assert not raport.acceptabila


def test_reflexie_locala_pe_buletin():
    """
    O pata concentrata de blit, pe o poza altfel corect expusa. Un procent
    global de pixeli albi n-ar distinge asta de o poza doar putin mai
    luminoasa; grila grosiera din _reflexie_locala o prinde.
    """
    generator = np.random.default_rng(3)
    arr = np.clip(generator.normal(120, 30, (1200, 1200, 3)), 0, 255)
    arr[400:560, 400:560] = 255  # blitul in folie, > un bloc intreg

    raport = calitate_poza.analizeaza_document(_poza(arr))

    assert "reflexie" in coduri(raport)


def test_buletin_bun_trece(fara_detector):
    raport = calitate_poza.analizeaza_document(_zgomot(latura=1200))

    assert raport.acceptabila
    assert coduri(raport) == []


# --- Cazuri degenerate ------------------------------------------------------


def test_imagine_ilizibila():
    raport = calitate_poza.analizeaza_selfie(b"nu sunt o poza")

    assert not raport.acceptabila
    assert coduri(raport) == ["ilizibila"]


# --- Ruta -------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """Detectorul e inlocuit: ruta se testeaza pentru forma raspunsului, nu pentru yunet."""
    monkeypatch.setattr(calitate_poza, "_detecteaza_fete", lambda arr: [_fata()])

    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _trimite(client, continut: bytes, tip: str = "selfie"):
    return client.post(
        "/api/identity/check-photo",
        files={"imagine": ("poza.png", continut, "image/png")},
        data={"tip": tip},
    )


def test_ruta_intoarce_problemele_fara_metrici(client):
    raspuns = _trimite(client, _uniforma(0))

    assert raspuns.status_code == 200
    corp = raspuns.json()
    assert corp["acceptabila"] is False
    assert corp["probleme"][0]["cod"] == "prea_intunecata"
    assert corp["probleme"][0]["mesaj"]
    # Numerele masurate raman in loguri, nu pleaca spre un client neautentificat.
    assert "metrici" not in corp


def test_ruta_accepta_o_poza_buna(client):
    raspuns = _trimite(client, _zgomot())

    assert raspuns.status_code == 200
    assert raspuns.json() == {"acceptabila": True, "probleme": []}


def test_ruta_refuza_un_fisier_gol(client):
    """422 + plicul standard, ca orice ValidationError (core/errors.py)."""
    raspuns = _trimite(client, b"")

    assert raspuns.status_code == 422
    assert raspuns.json()["error"]["code"] == "VALIDATION_ERROR"
