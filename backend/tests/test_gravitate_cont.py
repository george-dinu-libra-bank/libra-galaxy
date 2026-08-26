"""Ordonarea conturilor in lista administratorului.

Severitatea unei constatari si gravitatea unui cont raspund la intrebari
diferite: "cat de grava e aceasta plata" fata de "pe cine ma uit primul".
Testele de aici apara a doua intrebare.
"""

from app.ml.neregularitati import Neregularitate
from app.services.raport_service import gravitate_cont


def _constatari(cate: int, cea_mai_grava: int, suma_totala: float) -> list[Neregularitate]:
    per_bucata = suma_totala / cate
    return [
        Neregularitate(
            id_tranzactie=str(i),
            data="2026-08-21",
            suma=per_bucata,
            valuta="RON",
            comerciant="comerciant",
            tip="suma_neobisnuita",
            explicatie="",
            scor=cea_mai_grava if i == 0 else 40,
        )
        for i in range(cate)
    ]


def test_un_cont_fara_constatari_nu_are_gravitate() -> None:
    assert gravitate_cont([]) == 0


def test_multe_semnalari_si_multi_bani_bat_o_singura_plata_grava() -> None:
    """Cazul care a scos la iveala problema.

    Un cont cu o singura plata dublata de 1.400 de lei aparea inaintea unuia cu
    19 semnalari insumand 100 de milioane, fiindca dublarea confirmata are cea
    mai mare severitate. Cea mai grava plata a lui era intr-adevar mai putin
    grava, dar contul era clar mai urgent.
    """
    putin_dar_grav = gravitate_cont(_constatari(5, 95, 1_400.52))
    mult_si_mare = gravitate_cont(_constatari(19, 90, 100_230_740.78))

    assert mult_si_mare > putin_dar_grav


def test_la_fel_de_grave_decide_numarul() -> None:
    putine = gravitate_cont(_constatari(3, 95, 10_000.0))
    multe = gravitate_cont(_constatari(15, 95, 10_000.0))

    assert multe > putine


def test_la_fel_de_multe_decide_suma() -> None:
    putini_bani = gravitate_cont(_constatari(6, 80, 5_000.0))
    multi_bani = gravitate_cont(_constatari(6, 80, 5_000_000.0))

    assert multi_bani > putini_bani


def test_banii_singuri_nu_fac_un_cont_grav() -> None:
    """Volumul amplifica gravitatea, nu o creeaza.

    O singura constatare usoara pe o suma mare nu trebuie sa ajunga in capul
    listei peste conturi cu probleme adevarate.
    """
    o_suma_mare_usoara = gravitate_cont(_constatari(1, 25, 50_000_000.0))
    ceva_chiar_grav = gravitate_cont(_constatari(8, 95, 20_000.0))

    assert ceva_chiar_grav > o_suma_mare_usoara


def test_gravitatea_ramane_pe_scara_1_100() -> None:
    extrem = gravitate_cont(_constatari(500, 100, 10_000_000_000.0))
    minim = gravitate_cont(_constatari(1, 1, 0.01))

    assert 1 <= minim <= 100
    assert 1 <= extrem <= 100
