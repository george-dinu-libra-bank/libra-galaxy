"""Scorecard-ul: scara, praguri, si monotonia — proprietatea care conteaza.

Monotonia e cel mai valoros test de aici. Un scorecard in care inrautatirea unui
factor poate creste scorul e rupt, chiar daca toate exemplele punctuale ies bine,
iar bug-ul se vede abia cand cineva contesta o decizie.
"""

from decimal import Decimal

import pytest

from app.credit.scorecard import (
    DECIZIE_APROBAT,
    DECIZIE_ANALIZA_MANUALA,
    DECIZIE_RESPINS,
    PRAG_APROBARE,
    PRAG_ANALIZA_MANUALA,
    PUNCTE_COMPORTAMENT,
    PUNCTE_DOVADA_VENIT,
    PUNCTE_DTI,
    PUNCTE_MARJA_VENIT,
    PUNCTE_RELATIE,
    PUNCTE_VECHIME,
    DateScoring,
    calculeaza,
    decizie_pentru,
)


def _date(**modificari) -> DateScoring:
    implicit = dict(
        dti=Decimal("0.20"),
        venit_net=Decimal("6200"),
        venit_minim_produs=Decimal("3000"),
        vechime_angajator_luni=18,
        incredere_venit=0.9,
        luni_de_la_deschiderea_contului=14,
        neregularitati_recente=1,
    )
    return DateScoring(**{**implicit, **modificari})


def _puncte(scor, cod: str) -> int:
    return next(factor.puncte for factor in scor.factori if factor.cod == cod)


def test_scara_e_de_o_suta_de_puncte() -> None:
    """Pragurile (70/45) presupun scara asta; daca cineva schimba ponderile fara
    sa schimbe pragurile, testul cade aici, nu in productie."""
    assert (
        PUNCTE_DTI + PUNCTE_MARJA_VENIT + PUNCTE_VECHIME
        + PUNCTE_DOVADA_VENIT + PUNCTE_RELATIE + PUNCTE_COMPORTAMENT
    ) == 100


def test_dosarul_perfect_ia_suta() -> None:
    scor = calculeaza(_date(
        dti=Decimal("0"), venit_net=Decimal("9000"), vechime_angajator_luni=48,
        incredere_venit=1.0, luni_de_la_deschiderea_contului=36, neregularitati_recente=0,
    ))

    assert scor.total == 100
    assert scor.decizie == DECIZIE_APROBAT
    assert scor.aprobat


def test_dosarul_cel_mai_slab_ia_zero() -> None:
    scor = calculeaza(_date(
        dti=Decimal("0.40"), venit_net=Decimal("3000"), vechime_angajator_luni=0,
        incredere_venit=0.0, luni_de_la_deschiderea_contului=0, neregularitati_recente=9,
    ))

    assert scor.total == 0
    assert scor.decizie == DECIZIE_RESPINS


def test_scorul_ramane_mereu_in_scara() -> None:
    """Valori absurde nu trebuie sa sparga plafonul sau sa dea negativ."""
    extrem = calculeaza(_date(
        dti=Decimal("-1"), venit_net=Decimal("999999"), vechime_angajator_luni=600,
        incredere_venit=5.0, luni_de_la_deschiderea_contului=999, neregularitati_recente=-3,
    ))

    assert 0 <= extrem.total <= 100


# ---------------------------------------------------------------------------
# Monotonie: inrautatirea unui factor nu poate creste scorul
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dti", ["0", "0.05", "0.10", "0.20", "0.30", "0.35", "0.40"])
def test_dti_mai_mare_nu_da_niciodata_scor_mai_mare(dti) -> None:
    scoruri = [calculeaza(_date(dti=Decimal(d))).total
               for d in ["0", "0.05", "0.10", "0.20", "0.30", "0.35", "0.40"]]

    assert scoruri == sorted(scoruri, reverse=True)


def test_mai_multe_neregularitati_nu_dau_scor_mai_mare() -> None:
    scoruri = [calculeaza(_date(neregularitati_recente=n)).total for n in range(0, 8)]

    assert scoruri == sorted(scoruri, reverse=True)


def test_mai_multa_vechime_nu_da_scor_mai_mic() -> None:
    scoruri = [calculeaza(_date(vechime_angajator_luni=v)).total for v in range(0, 60, 6)]

    assert scoruri == sorted(scoruri)


def test_venit_mai_mare_nu_da_scor_mai_mic() -> None:
    scoruri = [calculeaza(_date(venit_net=Decimal(v))).total
               for v in ["3000", "4000", "6000", "9000", "12000"]]

    assert scoruri == sorted(scoruri)


def test_venit_mai_bine_dovedit_nu_da_scor_mai_mic() -> None:
    scoruri = [calculeaza(_date(incredere_venit=i)).total for i in [0.0, 0.25, 0.5, 0.75, 1.0]]

    assert scoruri == sorted(scoruri)


# ---------------------------------------------------------------------------
# Praguri si explicatii
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "total,asteptat",
    [
        (100, DECIZIE_APROBAT), (PRAG_APROBARE, DECIZIE_APROBAT),
        (PRAG_APROBARE - 1, DECIZIE_ANALIZA_MANUALA),
        (PRAG_ANALIZA_MANUALA, DECIZIE_ANALIZA_MANUALA),
        (PRAG_ANALIZA_MANUALA - 1, DECIZIE_RESPINS), (0, DECIZIE_RESPINS),
    ],
)
def test_pragurile_de_decizie_sunt_inclusive_in_jos(total, asteptat) -> None:
    assert decizie_pentru(total) == asteptat


def test_zona_gri_exista_si_trimite_la_om() -> None:
    """Un dosar mediocru dar nu rau nu se respinge automat: venit peste minim,
    indatorare inca sub plafon, vechime scurta si venit dovedit doar partial."""
    scor = calculeaza(_date(
        dti=Decimal("0.28"), venit_net=Decimal("4500"), vechime_angajator_luni=12,
        incredere_venit=0.7, luni_de_la_deschiderea_contului=10, neregularitati_recente=1,
    ))

    assert scor.decizie == DECIZIE_ANALIZA_MANUALA
    assert not scor.aprobat


def test_fiecare_factor_isi_spune_punctajul_si_motivul() -> None:
    """Un scor fara explicatie nu poate fi contestat si nici aparat."""
    scor = calculeaza(_date())

    assert len(scor.factori) == 6
    assert {f.cod for f in scor.factori} == {
        "dti", "marja_venit", "vechime_angajator", "dovada_venit", "relatie_banca", "comportament",
    }
    for factor in scor.factori:
        assert 0 <= factor.puncte <= factor.maxim
        assert len(factor.explicatie) > 10


def test_totalul_e_suma_factorilor() -> None:
    scor = calculeaza(_date())

    assert scor.total == sum(factor.puncte for factor in scor.factori)


def test_dti_e_factorul_cu_cea_mai_mare_pondere() -> None:
    """Capacitatea de rambursare cantareste mai mult decat orice altceva."""
    assert PUNCTE_DTI > max(
        PUNCTE_MARJA_VENIT, PUNCTE_VECHIME, PUNCTE_DOVADA_VENIT, PUNCTE_RELATIE, PUNCTE_COMPORTAMENT
    )


def test_venit_doar_declarat_pierde_tot_factorul_de_dovada() -> None:
    doar_declarat = calculeaza(_date(incredere_venit=0.0))
    din_tranzactii = calculeaza(_date(incredere_venit=1.0))

    assert _puncte(doar_declarat, "dovada_venit") == 0
    assert _puncte(din_tranzactii, "dovada_venit") == PUNCTE_DOVADA_VENIT


def test_dosarul_solid_se_aproba_singur_nu_ajunge_la_om() -> None:
    """Regresie: cu punctele de saturatie initiale (36 luni vechime, venit 3x),
    dosarul asta lua 59 si mergea la analiza manuala. Un salariat cu 6.200 RON
    net, indatorare 20% si venit confirmat din incasari nu are ce cauta acolo."""
    scor = calculeaza(_date(
        dti=Decimal("0.20"), venit_net=Decimal("6200"), vechime_angajator_luni=18,
        incredere_venit=0.9, luni_de_la_deschiderea_contului=14, neregularitati_recente=1,
    ))

    assert scor.total >= PRAG_APROBARE
    assert scor.decizie == DECIZIE_APROBAT
