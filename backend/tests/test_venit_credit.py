"""Detectia venitului: ce trebuie sa gaseasca si, mai important, ce nu.

Un fals-pozitiv aici e mai scump decat un fals-negativ: daca ratam salariul,
clientul incarca o adeverinta; daca luam drept salariu niste transferuri de la
un prieten, banca acorda credit pe un venit care nu exista.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.credit.venit import PRAG_DEVIATIE, detecteaza_venit
from app.ml.caracteristici import Plata

START = datetime(2025, 9, 25, 10, 0, tzinfo=timezone.utc)


def _incasare(zi: float, suma: float, platitor: str = "acme srl salariu") -> Plata:
    return Plata(
        id=str(uuid4()),
        moment=START + timedelta(days=zi),
        suma=suma,
        valuta="RON",
        comerciant=platitor,
        iesire=False,
    )


def _salariu(luni: int, suma: float = 6200.0, platitor: str = "acme srl salariu") -> list[Plata]:
    """Un sir lunar realist: ziua oscileaza cu +/-2 zile, suma cu cativa lei."""
    abateri_zi = [0, 1, -1, 2, 0, -2, 1, 0, -1, 1, 0, 2]
    abateri_suma = [0, 12, -8, 0, 20, -15, 5, 0, -10, 8, 0, -5]
    return [
        _incasare(30 * luna + abateri_zi[luna % 12], suma + abateri_suma[luna % 12], platitor)
        for luna in range(luni)
    ]


def test_gaseste_salariul_intr_un_istoric_realist() -> None:
    rezultat = detecteaza_venit(_salariu(12))

    assert rezultat is not None
    assert rezultat.platitor == "acme srl salariu"
    assert 6180 <= rezultat.venit_lunar <= 6220
    assert rezultat.luni_detectate == 12
    assert rezultat.incredere > 0.8


def test_nu_ia_transferuri_intamplatoare_drept_venit() -> None:
    """Acelasi platitor, dar fara ritm si cu sume imprastiate."""
    haotice = [
        _incasare(3, 150.0, "andrei"),
        _incasare(9, 1200.0, "andrei"),
        _incasare(41, 80.0, "andrei"),
        _incasare(44, 640.0, "andrei"),
        _incasare(97, 310.0, "andrei"),
    ]

    assert detecteaza_venit(haotice) is None


def test_sume_egale_dar_fara_ritm_lunar_nu_sunt_venit() -> None:
    """Trei plati identice in aceeasi saptamana nu sunt un salariu."""
    dese = [_incasare(0, 900.0, "chirie"), _incasare(2, 900.0, "chirie"), _incasare(5, 900.0, "chirie")]

    assert detecteaza_venit(dese) is None


def test_ritm_lunar_dar_sume_imprastiate_nu_sunt_venit() -> None:
    variabile = [
        _incasare(0, 1000.0, "colaborare"),
        _incasare(30, 4200.0, "colaborare"),
        _incasare(60, 800.0, "colaborare"),
        _incasare(90, 5100.0, "colaborare"),
    ]

    assert detecteaza_venit(variabile) is None


def test_platile_de_iesire_sunt_ignorate() -> None:
    """O rata lunara constanta catre acelasi comerciant e tot un tipar lunar
    stabil — dar e o cheltuiala, nu un venit."""
    iesiri = [
        Plata(id=str(uuid4()), moment=START + timedelta(days=30 * luna), suma=6200.0,
              valuta="RON", comerciant="acme srl salariu", iesire=True)
        for luna in range(12)
    ]

    assert detecteaza_venit(iesiri) is None


def test_sub_trei_incasari_nu_se_pronunta() -> None:
    assert detecteaza_venit(_salariu(2)) is None
    assert detecteaza_venit(_salariu(3)) is not None


def test_alege_salariul_nu_venitul_secundar() -> None:
    """Doua surse ambele regulate: castiga cea care duce greul."""
    rezultat = detecteaza_venit(_salariu(12) + _salariu(12, suma=900.0, platitor="chirias"))

    assert rezultat is not None
    assert rezultat.platitor == "acme srl salariu"


def test_increderea_creste_cu_istoricul() -> None:
    scurt = detecteaza_venit(_salariu(3))
    lung = detecteaza_venit(_salariu(12))

    assert scurt is not None and lung is not None
    assert lung.incredere > scurt.incredere


def test_deviatia_raportata_e_sub_prag_cand_accepta() -> None:
    rezultat = detecteaza_venit(_salariu(12))

    assert rezultat is not None
    assert rezultat.deviatie_relativa <= PRAG_DEVIATIE


def test_fara_incasari_nu_intoarce_nimic() -> None:
    assert detecteaza_venit([]) is None
