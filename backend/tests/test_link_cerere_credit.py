"""Butonul din chat trebuie sa deschida formularul COMPLETAT.

Cele doua capete se potriveau de la inceput: `prepare_credit_application`
construieste un link cu suma, durata, venit, angajator, vechime si obligatii
(tools/credit_tools.py), iar pagina /credite/cerere citeste fix acei parametri.
Ce lipsea era mijlocul — orchestratorul punea in `quick_action` constanta goala
`/credite/cerere` si arunca link-ul pregatit.

Efectul nu era doar „formular necompletat": pagina cere suma si durata valide,
altfel face redirect la simulator. Adica butonul te scotea din ecranul in care
tocmai ceruse-si sa intri.
"""

from __future__ import annotations

import pytest

from app.orchestration.orchestrator import _CREDIT_URL, _INTENTII_CREDIT, _link_cerere_credit
from app.tools.base import ToolResult


def _rezultat(date: dict | None, *, success: bool = True) -> ToolResult:
    return ToolResult(tool_name="prepare_credit_application", success=success, data=date)


def test_linkul_pregatit_de_tool_ajunge_in_buton() -> None:
    link = "/credite/cerere?suma=30000&luni=48&venit=5200&angajator=ACME+Software"

    assert _link_cerere_credit([_rezultat({"ready": True, "link": link})]) == link


def test_fara_date_complete_se_cade_pe_formularul_gol() -> None:
    """`ready: false` inseamna ca tool-ul inca cere date. Formularul gol e atunci
    raspunsul corect — omul il completeaza singur, ca inainte."""
    lipsa = _rezultat({"ready": False, "missing": ["venitul lunar net"]})

    assert _link_cerere_credit([lipsa]) == _CREDIT_URL


@pytest.mark.parametrize(
    "rezultate",
    [
        [],
        [_rezultat(None)],
        [_rezultat({"ready": True}, success=True)],          # link lipsa
        [_rezultat({"ready": True, "link": 42})],            # link de alt tip
        [_rezultat({"ready": True, "link": "/x"}, success=False)],
    ],
)
def test_nu_se_inventeaza_niciodata_un_link(rezultate) -> None:
    """Singura sursa e rezultatul tool-ului, ca la transfer. Orice altceva —
    inclusiv un tool care a esuat — cade pe URL-ul gol, niciodata pe ceva ghicit."""
    assert _link_cerere_credit(rezultate) == _CREDIT_URL


def test_butonul_se_ataseaza_la_ambele_intentii_de_creditare() -> None:
    """`credit_question` lipsea, desi ea prinde frazele cele mai concrete —
    „vreau sa depun o cerere de credit de 30000 pe 48 de luni" — adica exact
    cazurile in care formularul chiar se poate completa."""
    assert "credit_intent" in _INTENTII_CREDIT
    assert "credit_question" in _INTENTII_CREDIT
