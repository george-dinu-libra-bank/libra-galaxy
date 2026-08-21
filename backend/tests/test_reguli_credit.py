"""Criteriile hard: fiecare respinge cu codul corect, si nimic nu trece pe furis.

Limitele de varsta se testeaza pe zi exacta. O eroare de o zi acolo respinge un
om de 21 de ani fix sau accepta unul de 70 de ani si o zi — genul de bug care nu
se vede la testare cu date rotunde.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.credit.reguli import (
    PRAG_DTI,
    Motiv,
    Produs,
    Solicitant,
    grad_indatorare,
    varsta_din_cnp,
    verifica,
)

AZI = date(2026, 8, 20)

# Galaxy Flex Personal, exact ca randul din credit_produse.
FLEX = Produs(
    slug="galaxy-flex-personal",
    nume="Galaxy Flex Personal",
    dobanda_anuala=Decimal("0.0990"),
    suma_min=Decimal("5000"),
    suma_max=Decimal("150000"),
    luni_min=6,
    luni_max=60,
    varsta_min=21,
    varsta_max=70,
    venit_net_minim=Decimal("3000"),
    vechime_angajator_luni=6,
    vechime_venituri_luni=12,
)

# Nascut 1990-05-15, barbat. Cifra de control nu conteaza: modulul verifica
# formatul si data, validarea completa a CNP-ului se face la inregistrare.
CNP_35_ANI = "1900515123456"


def _solicitant(**modificari) -> Solicitant:
    implicit = dict(
        cnp=CNP_35_ANI,
        verification_status="verified",
        venit_net=Decimal("6200"),
        obligatii_lunare=Decimal("0"),
        vechime_angajator_luni=18,
        vechime_venituri_luni=24,
    )
    return Solicitant(**{**implicit, **modificari})


def _coduri(motive: list[Motiv]) -> set[str]:
    return {motiv.cod for motiv in motive}


def _verifica(**modificari) -> list[Motiv]:
    suma = modificari.pop("suma", Decimal("50000"))
    luni = modificari.pop("luni", 36)
    rata = modificari.pop("rata_lunara", Decimal("1611.01"))
    return verifica(FLEX, _solicitant(**modificari), suma, luni, rata, la_data=AZI)


# ---------------------------------------------------------------------------
# Varsta din CNP
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cnp,varsta_asteptata",
    [
        ("1900515123456", 36),  # 1990-05-15, ziua a trecut anul asta
        ("1901215123456", 35),  # 1990-12-15, ziua nu a venit inca
        ("5050820123456", 21),  # 2005-08-20, implineste exact azi
        ("5050821123456", 20),  # 2005-08-21, ii mai trebuie o zi
        ("1560820123456", 70),  # 1956-08-20, implineste exact azi
        ("1550820123456", 71),  # 1955-08-20
        ("3010101123456", 225), # 1801-01-01, cifra 3 = secolul XIX
    ],
)
def test_varsta_derivata_din_cnp(cnp, varsta_asteptata) -> None:
    assert varsta_din_cnp(cnp, AZI) == varsta_asteptata


def test_cnp_de_rezident_strain_alege_secolul_plauzibil() -> None:
    """7 si 8 nu au regula de secol fixata prin lege — se ia varianta posibila."""
    assert varsta_din_cnp("7900515123456", AZI) == 36


@pytest.mark.parametrize("cnp", ["123", "19005151234567", "abcdefghijklm", "1903015123456", "1901340123456"])
def test_cnp_imposibil_e_respins(cnp) -> None:
    with pytest.raises(ValueError):
        varsta_din_cnp(cnp, AZI)


# ---------------------------------------------------------------------------
# Gradul de indatorare
# ---------------------------------------------------------------------------


def test_rata_noua_intra_in_calculul_dti() -> None:
    """Intrebarea nu e daca omul isi permite ce are, ci si ce cere."""
    fara = grad_indatorare(Decimal("6000"), Decimal("600"), Decimal("0"))
    cu = grad_indatorare(Decimal("6000"), Decimal("600"), Decimal("1200"))

    assert fara == Decimal("0.1000")
    assert cu == Decimal("0.3000")


def test_venit_zero_nu_are_grad_de_indatorare() -> None:
    with pytest.raises(ValueError):
        grad_indatorare(Decimal("0"), Decimal("100"), Decimal("100"))


# ---------------------------------------------------------------------------
# Verificarea completa
# ---------------------------------------------------------------------------


def test_dosarul_bun_nu_are_niciun_motiv_de_respingere() -> None:
    assert _verifica() == []


def test_fiecare_criteriu_respinge_cu_codul_lui() -> None:
    assert "varsta_neeligibila" in _coduri(_verifica(cnp="5050821123456"))
    assert "venit_sub_minim" in _coduri(_verifica(venit_net=Decimal("2400")))
    assert "vechime_angajator_insuficienta" in _coduri(_verifica(vechime_angajator_luni=3))
    assert "vechime_venituri_insuficienta" in _coduri(_verifica(vechime_venituri_luni=8))
    assert "identitate_neverificata" in _coduri(_verifica(verification_status="pending"))
    assert "suma_in_afara_limitelor" in _coduri(_verifica(suma=Decimal("200000")))
    assert "suma_in_afara_limitelor" in _coduri(_verifica(suma=Decimal("1000")))
    assert "perioada_in_afara_limitelor" in _coduri(_verifica(luni=72))
    assert "perioada_in_afara_limitelor" in _coduri(_verifica(luni=3))
    assert "cnp_invalid" in _coduri(_verifica(cnp="nuemcnp"))


def test_limitele_produsului_sunt_inclusive() -> None:
    """Exact 5.000 RON pe exact 6 luni trebuie sa treaca, nu sa pice la limita."""
    assert _coduri(_verifica(suma=Decimal("5000"), luni=6, rata_lunara=Decimal("857"))) == set()
    assert _coduri(_verifica(suma=Decimal("150000"), luni=60, rata_lunara=Decimal("3175"),
                             venit_net=Decimal("20000"))) == set()


def test_gradul_de_indatorare_peste_plafon_respinge() -> None:
    """Venit peste minim, dar obligatii care nu lasa loc de inca o rata."""
    motive = _verifica(venit_net=Decimal("4000"), obligatii_lunare=Decimal("900"))

    assert "grad_indatorare_depasit" in _coduri(motive)
    assert "venit_sub_minim" not in _coduri(motive)


def test_exact_pe_plafonul_de_indatorare_trece() -> None:
    """DTI fix 40% e acceptat; plafonul e "cel mult", nu "sub"."""
    motive = _verifica(venit_net=Decimal("10000"), obligatii_lunare=Decimal("2400"),
                       rata_lunara=Decimal("1600"))

    assert grad_indatorare(Decimal("10000"), Decimal("2400"), Decimal("1600")) == PRAG_DTI
    assert "grad_indatorare_depasit" not in _coduri(motive)


def test_motivele_se_aduna_toate_deodata() -> None:
    """Clientul afla tot ce il impiedica dintr-o data, nu pe rand la fiecare
    incercare."""
    motive = _verifica(
        cnp="5050821123456", venit_net=Decimal("1500"), vechime_angajator_luni=1,
        vechime_venituri_luni=2, verification_status="pending", suma=Decimal("900000"), luni=120,
    )

    assert _coduri(motive) >= {
        "varsta_neeligibila", "venit_sub_minim", "vechime_angajator_insuficienta",
        "vechime_venituri_insuficienta", "identitate_neverificata",
        "suma_in_afara_limitelor", "perioada_in_afara_limitelor",
    }


def test_motivele_au_text_citibil_nu_doar_cod() -> None:
    """Textul ajunge in fata clientului cand nu e disponibil un model de limbaj."""
    motive = _verifica(venit_net=Decimal("2400"))

    assert all(len(motiv.text) > 20 and motiv.text[0].isupper() for motiv in motive)
    assert any("3.000" in motiv.text or "3,000" in motiv.text for motiv in motive)
