"""Graficul de rambursare: invariantii care trebuie sa tina la orice parametri.

Un test gresit aici ar valida o formula gresita, iar un grafic gresit se vede
abia peste luni, in soldul care nu se inchide. De aceea majoritatea testelor
verifica proprietati (suma principalelor = creditul acordat), nu numere pe care
le-am calculat tot eu si care ar putea fi gresite in acelasi fel ca implementarea.
"""

from decimal import Decimal

import pytest

from app.credit.amortizare import (
    bani_din_lei,
    cost_rambursare_anticipata,
    dae,
    genereaza_grafic,
    lei_din_bani,
    rata_lunara_bani,
    sold_dupa,
)

# Galaxy Flex Personal, exemplul din plan: 50.000 RON pe 36 de luni la 9,90%.
PRINCIPAL = 5_000_000  # bani
DOBANDA = Decimal("0.099")
LUNI = 36

# Combinatii pe care se verifica invariantii — inclusiv capetele intervalului de
# produs (5.000-150.000 RON, 6-60 luni) si dobanda zero.
PARAMETRI = [
    (500_000, Decimal("0.099"), 6),
    (PRINCIPAL, DOBANDA, LUNI),
    (15_000_000, Decimal("0.099"), 60),
    (1_234_567, Decimal("0.0549"), 47),  # sume si perioade "urate", dinadins
    (5_000_000, Decimal("0"), 24),
    (100_000, Decimal("0.35"), 60),  # dobanda mare, perioada lunga
]


@pytest.mark.parametrize("principal,dobanda,luni", PARAMETRI)
def test_graficul_se_inchide_exact_pe_zero(principal, dobanda, luni) -> None:
    """Invariantul care conteaza cel mai mult: creditul se poate inchide."""
    grafic = genereaza_grafic(principal, dobanda, luni)

    assert len(grafic) == luni
    assert grafic[-1].sold_dupa_bani == 0


@pytest.mark.parametrize("principal,dobanda,luni", PARAMETRI)
def test_suma_principalelor_e_exact_creditul_acordat(principal, dobanda, luni) -> None:
    """Nici un ban in plus, nici unul in minus — altfel banca da sau incaseaza
    bani pe care nu ii poate justifica."""
    grafic = genereaza_grafic(principal, dobanda, luni)

    assert sum(rata.principal_bani for rata in grafic) == principal


@pytest.mark.parametrize("principal,dobanda,luni", PARAMETRI)
def test_dobanda_e_diferenta_dintre_cat_plateste_si_cat_a_primit(principal, dobanda, luni) -> None:
    grafic = genereaza_grafic(principal, dobanda, luni)

    total_platit = sum(rata.total_bani for rata in grafic)
    total_dobanda = sum(rata.dobanda_bani for rata in grafic)

    assert total_dobanda == total_platit - principal


@pytest.mark.parametrize("principal,dobanda,luni", PARAMETRI)
def test_fiecare_linie_e_coerenta_in_sine(principal, dobanda, luni) -> None:
    """total = principal + dobanda pe fiecare rand, si soldul scade monoton."""
    grafic = genereaza_grafic(principal, dobanda, luni)
    sold_anterior = principal

    for rata in grafic:
        assert rata.total_bani == rata.principal_bani + rata.dobanda_bani
        assert rata.sold_dupa_bani == sold_anterior - rata.principal_bani
        assert rata.sold_dupa_bani < sold_anterior
        assert rata.principal_bani > 0
        assert rata.dobanda_bani >= 0
        sold_anterior = rata.sold_dupa_bani


def test_toate_ratele_in_afara_de_ultima_sunt_egale() -> None:
    """Asta e definitia anuitatii; ultima e cea care difera, si doar ea."""
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)
    rata = rata_lunara_bani(PRINCIPAL, DOBANDA, LUNI)

    assert {linie.total_bani for linie in grafic[:-1]} == {rata}


def test_ultima_rata_absoarbe_restul_din_rotunjiri() -> None:
    """Diferenta exista, e mica, si e in ultima rata — nu imprastiata prin grafic
    si nici pierduta."""
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)
    rata = rata_lunara_bani(PRINCIPAL, DOBANDA, LUNI)

    # Sub un leu: e rest de rotunjire, nu o eroare de formula.
    assert abs(grafic[-1].total_bani - rata) < 100


def test_dobanda_scade_si_principalul_creste_de_la_luna_la_luna() -> None:
    """Forma caracteristica a anuitatii: la inceput platesti mai ales dobanda."""
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)

    dobanzi = [rata.dobanda_bani for rata in grafic]
    principale = [rata.principal_bani for rata in grafic[:-1]]

    assert dobanzi == sorted(dobanzi, reverse=True)
    assert principale == sorted(principale)


def test_rata_corespunde_unei_implementari_independente() -> None:
    """Verificare incrucisata: aceeasi formula, dar in float, scrisa altfel.

    Nu inlocuieste implementarea (float-ul e exact motivul pentru care modulul
    lucreaza in Decimal), dar prinde o greseala de algebra — un semn de exponent
    inversat n-ar trece pe amandoua caile.
    """
    i = 0.099 / 12
    asteptat = PRINCIPAL * i / (1 - (1 + i) ** -LUNI)

    assert abs(rata_lunara_bani(PRINCIPAL, DOBANDA, LUNI) - asteptat) <= 1


def test_fara_dobanda_rata_e_simpla_impartire() -> None:
    grafic = genereaza_grafic(5_000_000, Decimal("0"), 25)

    assert rata_lunara_bani(5_000_000, Decimal("0"), 25) == 200_000
    assert all(rata.dobanda_bani == 0 for rata in grafic)
    assert sum(rata.total_bani for rata in grafic) == 5_000_000


def test_dobanda_data_ca_float_sau_text_da_acelasi_rezultat() -> None:
    """`Decimal(0.099)` ar aduce artefactele binare ale lui float in calcul."""
    din_decimal = rata_lunara_bani(PRINCIPAL, Decimal("0.099"), LUNI)

    assert rata_lunara_bani(PRINCIPAL, 0.099, LUNI) == din_decimal
    assert rata_lunara_bani(PRINCIPAL, "0.099", LUNI) == din_decimal


# ---------------------------------------------------------------------------
# DAE
# ---------------------------------------------------------------------------


def test_dae_depaseste_dobanda_nominala_din_capitalizare() -> None:
    """Fara niciun comision, 9,90% nominal inseamna 10,36% efectiv."""
    rata = rata_lunara_bani(PRINCIPAL, DOBANDA, LUNI)
    rezultat = dae(PRINCIPAL, rata, LUNI)

    assert rezultat > DOBANDA
    assert abs(rezultat - Decimal("0.103618")) < Decimal("0.0001")


def test_dae_creste_cu_comisioanele() -> None:
    """Un comision retinut la acordare inseamna mai putini bani primiti pentru
    aceleasi rate, deci un cost real mai mare."""
    rata = rata_lunara_bani(PRINCIPAL, DOBANDA, LUNI)

    assert dae(PRINCIPAL, rata, LUNI, comisioane_bani=100_000) > dae(PRINCIPAL, rata, LUNI)


def test_dae_refuza_ce_nu_poate_calcula() -> None:
    rata = rata_lunara_bani(PRINCIPAL, DOBANDA, LUNI)

    with pytest.raises(ValueError):
        dae(PRINCIPAL, rata, LUNI, comisioane_bani=PRINCIPAL)
    with pytest.raises(ValueError):
        # Rate care nu acopera nici macar principalul: nu exista dobanda pozitiva.
        dae(PRINCIPAL, 1, LUNI)


# ---------------------------------------------------------------------------
# Sold si rambursare anticipata
# ---------------------------------------------------------------------------


def test_sold_dupa_zero_rate_e_principalul() -> None:
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)

    assert sold_dupa(grafic, 0) == PRINCIPAL
    assert sold_dupa(grafic, LUNI) == 0


def test_sold_dupa_respinge_valori_din_afara_graficului() -> None:
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)

    with pytest.raises(ValueError):
        sold_dupa(grafic, LUNI + 1)
    with pytest.raises(ValueError):
        sold_dupa(grafic, -1)


def test_rambursarea_anticipata_economiseste_dobanda() -> None:
    """La jumatatea perioadei, dobanda ramasa de plata e substantiala — exact
    motivul pentru care cineva ramburseaza anticipat."""
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)
    cost = cost_rambursare_anticipata(grafic, rate_platite=18, zile_de_la_ultima_scadenta=0, dobanda_anuala=DOBANDA)

    assert cost.sold_bani == grafic[17].sold_dupa_bani
    assert cost.dobanda_acumulata_bani == 0
    assert cost.total_bani == cost.sold_bani
    assert cost.economie_dobanda_bani == sum(rata.dobanda_bani for rata in grafic[18:])


def test_dobanda_se_acumuleaza_pe_zile_nu_pe_luni_intregi() -> None:
    """Cine ramburseaza la 10 zile dupa scadenta plateste 10 zile, nu o luna."""
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)

    la_scadenta = cost_rambursare_anticipata(grafic, 12, 0, DOBANDA)
    dupa_10_zile = cost_rambursare_anticipata(grafic, 12, 10, DOBANDA)
    dupa_30_zile = cost_rambursare_anticipata(grafic, 12, 30, DOBANDA)

    assert la_scadenta.dobanda_acumulata_bani == 0
    assert 0 < dupa_10_zile.dobanda_acumulata_bani < dupa_30_zile.dobanda_acumulata_bani
    # Cu cat trece mai mult timp, cu atat se economiseste mai putin.
    assert dupa_10_zile.economie_dobanda_bani > dupa_30_zile.economie_dobanda_bani


def test_rambursarea_integrala_la_final_nu_mai_economiseste_nimic() -> None:
    grafic = genereaza_grafic(PRINCIPAL, DOBANDA, LUNI)
    cost = cost_rambursare_anticipata(grafic, LUNI, 0, DOBANDA)

    assert cost.sold_bani == 0
    assert cost.total_bani == 0
    assert cost.economie_dobanda_bani == 0


# ---------------------------------------------------------------------------
# Conversii si validari
# ---------------------------------------------------------------------------


def test_conversia_lei_bani_e_reversibila() -> None:
    assert bani_din_lei("1250.50") == 125_050
    assert lei_din_bani(125_050) == Decimal("1250.50")
    assert lei_din_bani(bani_din_lei("99999999.99")) == Decimal("99999999.99")


def test_rotunjirea_la_ban_merge_in_sus_la_jumatate() -> None:
    assert bani_din_lei("0.005") == 1
    assert bani_din_lei("0.004") == 0


@pytest.mark.parametrize(
    "principal,luni",
    [(0, 12), (-100, 12), (100_000, 0), (100_000, -6)],
)
def test_parametrii_imposibili_sunt_respinsi(principal, luni) -> None:
    with pytest.raises(ValueError):
        rata_lunara_bani(principal, DOBANDA, luni)
    with pytest.raises(ValueError):
        genereaza_grafic(principal, DOBANDA, luni)
