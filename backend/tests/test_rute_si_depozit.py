"""Rutele si depozitul trebuie sa cada la fel.

De ce exista fisierul asta: `admin_repository.py` are DOUA clase —
`AdminRepository` si `AnalizaRepository`. Metodele cozilor de cereri au fost
scrise, prin indentare, in a doua, iar rutele cheama prima. Nimic n-a semnalat-o:
Python nu verifica la import ca `depozit.cereri_stergere` exista, testele nu ating
rutele de admin, iar pagina din frontend facea `.catch(() => [])` — deci coada
aparea goala in loc sa dea eroare. Functia livrata nu mergea deloc.

Testul e ieftin si prinde exact clasa aia de greseala: o metoda mutata din
gresala intre clase, sau redenumita intr-un singur loc.
"""

from __future__ import annotations

import pytest

from app.repositories.admin_repository import AdminRepository, AnalizaRepository

# Ce cheama `api/routes/admin.py` pe `AdminRepository(client)`.
METODE_ADMIN = (
    "cereri_stergere",
    "decide_stergere",
    "sterge_client",
    "sterge_utilizator_auth",
    "cereri_inchidere_cont",
    "decide_inchidere_cont",
    "redeschide_cont",
)

# Ce cheama `AnalizaContService` pe `AnalizaRepository(client)`.
METODE_ANALIZA = ("scrie_analiza",)


@pytest.mark.parametrize("nume", METODE_ADMIN)
def test_adminrepository_are_ce_cer_rutele(nume: str) -> None:
    assert hasattr(AdminRepository, nume), (
        f"ruta cheama AdminRepository.{nume}, dar metoda nu e pe clasa asta — "
        "verifica indentarea, poate a ajuns in AnalizaRepository"
    )


@pytest.mark.parametrize("nume", METODE_ANALIZA)
def test_analizarepository_ramane_intreg(nume: str) -> None:
    assert hasattr(AnalizaRepository, nume)


@pytest.mark.parametrize("nume", METODE_ADMIN)
def test_cozile_nu_stau_pe_depozitul_de_analize(nume: str) -> None:
    """Si invers: daca ajung pe amandoua, inseamna ca cineva a copiat in loc sa mute."""
    assert not hasattr(AnalizaRepository, nume)
