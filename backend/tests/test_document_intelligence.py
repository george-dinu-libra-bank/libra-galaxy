"""Citirea adeverintelor prin Azure Document Intelligence.

Testele nu ating reteaua. Structurile de mai jos sunt copiate dintr-un raspuns
adevarat al resursei proiectului (prebuilt-layout, api-version 2024-11-30), pe
adeverinta de test „OCR" — inclusiv cele doua capcane care au dus la scrierea
acestui fisier:

1. `content` lipeste randuri pe care hartia le are separate;
2. un rand de tabel citit ca text plat da brutul, nu netul.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.credit.adeverinta import (
    angajator_din_tabele,
    citeste_adeverinta,
    vechime_din_tabele,
    venit_din_tabele,
)
from app.infrastructure import citire_adeverinta
from app.infrastructure.cnp import din_cuvinte
from app.providers.document_intelligence import TextCitit, _din_raspuns

# --- Capcana 1: `content` aplatizat vs `lines[]` -----------------------------

RASPUNS_AZURE = {
    "status": "succeeded",
    "analyzeResult": {
        "apiVersion": "2024-11-30",
        "modelId": "prebuilt-layout",
        # Azure lipeste aici randul brutului de al netului: le considera acelasi
        # paragraf. Pe hartie sunt doua randuri.
        "content": (
            "ADEVERINTA DE VENIT\n"
            "Salariul brut lunar: 14.500,00 lei Salariul net lunar: 8.700,00 lei"
        ),
        "pages": [
            {
                "pageNumber": 1,
                "lines": [
                    {"content": "ADEVERINTA DE VENIT"},
                    {"content": "Salariul brut lunar: 14.500,00 lei"},
                    {"content": "Salariul net lunar: 8.700,00 lei"},
                ],
                "words": [
                    {"content": "net", "confidence": 0.991},
                    {"content": "8.700,00", "confidence": 0.983},
                ],
            }
        ],
    },
}


def test_textul_vine_din_randuri_nu_din_aplatizare() -> None:
    """Din `content`, "brut" si "net" ajung pe aceeasi linie, iar adeverinta.py
    arunca linia intreaga cand vede "brut" — venitul se pierde pe un document
    citit perfect. Testul pastreaza ambele citiri, ca diferenta sa ramana
    vizibila, nu doar afirmata in comentarii."""
    din_lines = _din_raspuns(RASPUNS_AZURE).text
    din_content = RASPUNS_AZURE["analyzeResult"]["content"]

    assert citeste_adeverinta(din_lines).venit_net == Decimal("8700.00")
    assert citeste_adeverinta(din_content).venit_net is None


def test_cuvintele_pastreaza_increderea_raportata() -> None:
    cuvinte = _din_raspuns(RASPUNS_AZURE).cuvinte

    assert [c.text for c in cuvinte] == ["net", "8.700,00"]
    assert cuvinte[-1].incredere == pytest.approx(0.983)


def test_raspuns_gol_nu_arunca() -> None:
    assert _din_raspuns({}).text == ""
    assert _din_raspuns({"analyzeResult": {"pages": []}}).tabele == ()


def test_celulele_se_aseaza_in_grila_densa() -> None:
    """Azure da celulele ca lista plata, cu indici. O celula lipsa trebuie sa
    devina sir gol, altfel indicele de coloana nu mai inseamna acelasi lucru pe
    fiecare rand si alinierea antet-valoare devine falsa."""
    raspuns = {
        "analyzeResult": {
            "tables": [
                {
                    "rowCount": 2,
                    "columnCount": 3,
                    "cells": [
                        {"rowIndex": 0, "columnIndex": 0, "content": "a"},
                        {"rowIndex": 0, "columnIndex": 2, "content": "c"},
                        {"rowIndex": 1, "columnIndex": 1, "content": "Virament ban-\ncar"},
                    ],
                }
            ]
        }
    }

    assert _din_raspuns(raspuns).tabele == ((("a", "", "c"), ("", "Virament bancar", "")),)


# --- Capcana 2: coloana de tabel vs text plat --------------------------------

TABEL_VENITURI = (
    ("Lună / An", "Venit Brut (RON)", "Venit Net (RON)", "Rețineri/Popriri", "Mod Plată"),
    ("Iulie 2025", "14.500,00", "8.482,00", "0,00", "Virament bancar"),
    ("August 2025", "14.500,00", "8.482,00", "0,00", "Virament bancar"),
    ("Media Netă", "15.000,00", "8.774,50", "0,00", "—"),
)

TABEL_ANGAJATOR = (
    ("Câmp Date OCR", "Valoare Text"),
    ("Denumire Societate", "SC TECH SOLUTIONS DEVELOPMENT SRL"),
    ("Cont IBAN Angajator", "RO98 BTRL 0000 1234 5678 9012"),
)

TABEL_ANGAJAT = (
    ("Câmp Date OCR", "Valoare Text"),
    ("Vechime la locul actual", "3 ani și 4 luni (Data angajării: 01.09.2022)"),
)

TABELE = (TABEL_ANGAJATOR, TABEL_ANGAJAT, TABEL_VENITURI)

# Cum arata acelasi rand de tabel dupa aplatizare. Aici s-a nascut bugul.
TEXT_PLAT = "Media Netă 15.000,00 8.774,50 0,00 —"


def test_coloana_de_tabel_da_netul_iar_textul_plat_da_brutul() -> None:
    """Regresia care a pornit toata integrarea.

    Ca text plat, dupa eticheta "Netă" primul numar e al coloanei brutului, deci
    parserul propunea 15.000 drept venit — cifra pe care banca ar fi acordat un
    credit. Cu antetul in fata, nu mai e nimic de ghicit.
    """
    assert venit_din_tabele(TABELE) == Decimal("8774.50")
    assert citeste_adeverinta(TEXT_PLAT).venit_net == Decimal("15000.00")


def test_randul_de_medie_bate_lunile_individuale() -> None:
    assert venit_din_tabele((TABEL_VENITURI,)) == Decimal("8774.50")


def test_fara_rand_de_medie_se_face_media_coloanei() -> None:
    fara_medie = TABEL_VENITURI[:3]

    assert venit_din_tabele((fara_medie,)) == Decimal("8482.00")


def test_antetul_ambiguu_nu_se_alege() -> None:
    """„Total brut si net" spune si una si alta — regula casei: mai bine gol."""
    tabel = (("Luna", "Total brut si net"), ("Iulie", "9.000,00"))

    assert venit_din_tabele((tabel,)) is None


def test_angajatorul_vine_din_celula_nu_din_antet() -> None:
    """Ca text plat, `_cauta_angajator` citea antetul tabelului („Camp Date OCR")
    drept nume de firma. Si: "denumire societate" trebuie sa bata "angajator",
    altfel randul „Cont IBAN Angajator" ar da IBAN-ul drept nume."""
    assert angajator_din_tabele(TABELE) == "SC TECH SOLUTIONS DEVELOPMENT SRL"


def test_vechimea_include_si_lunile() -> None:
    """„3 ani si 4 luni" e 40, nu 36 — patru luni pierdute la fiecare citire."""
    assert vechime_din_tabele(TABELE) == 40


# --- CNP din cuvinte ---------------------------------------------------------


def test_cnp_dintr_un_singur_cuvant() -> None:
    cnp, incredere = din_cuvinte([("CNP", 0.99), ("1970101221144", 0.95)])

    assert cnp == "1970101221144"
    assert incredere == pytest.approx(0.95)


def test_cnp_rupt_intre_cuvinte_se_lipeste() -> None:
    """Motorul rupe uneori numarul; increderea devine media bucatilor."""
    cnp, incredere = din_cuvinte([("1970101", 0.90), ("221144", 0.80)])

    assert cnp == "1970101221144"
    assert incredere == pytest.approx(0.85)


def test_fara_cnp_nu_se_inventeaza() -> None:
    assert din_cuvinte([("Popescu", 0.99), ("12345", 0.99)]) == (None, 0.0)


# --- Orchestrarea: cine se cheama si cand ------------------------------------


class _SetariCuChei:
    document_intelligence_configured = True


class _FaraChei:
    document_intelligence_configured = False


def _azure_care_intoarce(citit: TextCitit):
    class _Azure:
        def __init__(self, *a, **k) -> None:
            pass

        async def citeste(self, *a, **k) -> TextCitit:
            return citit

    return _Azure


async def _local_fals(continut: bytes, content_type: str | None) -> str:
    return "Salariul net lunar: 1.234,00 lei"


async def test_azure_se_cheama_si_pentru_pdf_cu_strat_de_text(monkeypatch) -> None:
    """Decizie de cost, luata in cunostinta de cauza.

    S-ar putea citi intai stratul de text al PDF-ului, gratis si exact pe
    caractere. Dar caracterele nu sunt problema — structura e: pe o adeverinta
    in tabel, textul plat da brutul. Zece bani pe document sunt mai ieftini
    decat un venit gresit intr-un dosar de credit.
    """
    from tests.test_flux_credit_documente import _pdf_adeverinta

    citit = TextCitit(text="Salariul net lunar: 4.850,00 lei", cuvinte=(), tabele=())
    monkeypatch.setattr(citire_adeverinta, "get_settings", lambda: _SetariCuChei())
    monkeypatch.setattr(citire_adeverinta, "AzureDocumentIntelligence", _azure_care_intoarce(citit))
    monkeypatch.setattr(
        citire_adeverinta,
        "text_din_document",
        lambda *a, **k: pytest.fail("nu trebuia sa se cada pe citirea locala"),
    )

    date = await citire_adeverinta.citeste(_pdf_adeverinta(), "application/pdf")

    assert date.venit_net == Decimal("4850.00")


async def test_tabelul_bate_citirea_din_text(monkeypatch) -> None:
    """Cand exista si tabel, si text, tabelul castiga — si increderea creste."""
    citit = TextCitit(text=TEXT_PLAT, cuvinte=(), tabele=TABELE)
    monkeypatch.setattr(citire_adeverinta, "get_settings", lambda: _SetariCuChei())
    monkeypatch.setattr(citire_adeverinta, "AzureDocumentIntelligence", _azure_care_intoarce(citit))

    date = await citire_adeverinta.citeste(b"x", "application/pdf")

    assert date.venit_net == Decimal("8774.50")
    assert date.angajator == "SC TECH SOLUTIONS DEVELOPMENT SRL"
    assert date.vechime_luni == 40
    assert date.incredere == citire_adeverinta.INCREDERE_TABEL


async def test_fara_tabel_ramane_citirea_din_text(monkeypatch) -> None:
    """Adeverintele scrise curgator n-au ce coloana sa ofere."""
    citit = TextCitit(text="Salariul net lunar: 4.850,00 lei", cuvinte=(), tabele=())
    monkeypatch.setattr(citire_adeverinta, "get_settings", lambda: _SetariCuChei())
    monkeypatch.setattr(citire_adeverinta, "AzureDocumentIntelligence", _azure_care_intoarce(citit))

    date = await citire_adeverinta.citeste(b"x", "image/jpeg")

    assert date.venit_net == Decimal("4850.00")
    assert date.incredere < citire_adeverinta.INCREDERE_TABEL


async def test_fara_chei_se_cade_pe_citirea_locala(monkeypatch) -> None:
    monkeypatch.setattr(citire_adeverinta, "get_settings", lambda: _FaraChei())
    monkeypatch.setattr(citire_adeverinta, "text_din_document", _local_fals)

    date = await citire_adeverinta.citeste(b"x", "image/jpeg")

    assert date.venit_net == Decimal("1234.00")


async def test_azure_picat_cade_pe_citirea_locala(monkeypatch) -> None:
    """O pana la Azure nu se vede in interfata: documentul se citeste mai prost,
    dar se citeste. Fara asta, o incarcare de adeverinta ar esua cu 500."""
    from app.core.errors import AiProviderUnavailableError

    class _AzureCazut:
        def __init__(self, *a, **k) -> None:
            pass

        async def citeste(self, *a, **k):
            raise AiProviderUnavailableError("pana")

    monkeypatch.setattr(citire_adeverinta, "get_settings", lambda: _SetariCuChei())
    monkeypatch.setattr(citire_adeverinta, "AzureDocumentIntelligence", _AzureCazut)
    monkeypatch.setattr(citire_adeverinta, "text_din_document", _local_fals)

    date = await citire_adeverinta.citeste(b"x", "image/jpeg")

    assert date.venit_net == Decimal("1234.00")
