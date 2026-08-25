"""Creditele, vazute de asistent.

Pana acum niciun agent nu stia nimic despre ele: „de ce mi-a fost respinsa
cererea?" ajungea la RAG si primea brosura produsului, nu dosarul omului.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.security import Principal
from app.orchestration.intent import classify_intent
from app.tools.base import RiskLevel, SideEffect
from app.tools.credit_tools import build_credit_tools

# `Principal.user_id` e str, nu UUID — repository-ul face `str()` oricum.
ID_USER = "6d1eaaec-0000-4000-8000-000000000001"


class _RepoFals:
    def __init__(self) -> None:
        self.id_cerere = str(uuid4())
        self.id_credit = str(uuid4())

    async def cereri_utilizator(self, user_id):
        assert user_id == ID_USER  # tool-ul nu poate cere dosarul altcuiva
        return [{
            "id": self.id_cerere, "status": "respinsa", "suma_ceruta": "30000",
            "luni": 48, "rata_lunara": None, "creat_la": "2026-08-01T10:00:00Z",
            "oferta_expira_la": None, "scor": 41, "dti": "0.52",
            "explicatie": "Gradul de indatorare depaseste pragul.",
            "motive": [{"cod": "dti_prea_mare", "text": "DTI 52%"}],
            "venit_folosit": "4850", "obligatii_folosite": "1200",
        }]

    async def credite_utilizator(self, user_id):
        return [{
            "id": self.id_credit, "status": "activ", "principal": "20000",
            "sold_ramas": "17500", "rata_lunara": "512.34", "luni": 48,
            "dobanda_anuala": "0.099", "data_acordarii": "2026-06-01",
        }]

    async def rate(self, id_credit):
        return [
            {"numar": 1, "scadenta": "2026-07-01", "total": "512.34", "status": "platita"},
            {"numar": 2, "scadenta": "2026-08-01", "total": "512.34", "status": "scadenta"},
        ]

    async def produs(self, slug):
        return {"slug": slug, "dobanda_anuala": "0.099"}


def _tool(nume: str):
    unelte = {t.name: t for t in build_credit_tools(_RepoFals())}
    return unelte[nume]


PRINCIPAL = Principal(user_id=ID_USER, role="client", access_token="t")


async def test_toate_sunt_citire_si_risc_mic() -> None:
    """Asistentul explica ce s-a hotarat; nu hotaraste si nu misca bani."""
    for unealta in build_credit_tools(_RepoFals()):
        assert unealta.side_effect in (SideEffect.READ_ONLY, SideEffect.COMPUTE)
        assert unealta.risk_level is RiskLevel.LOW
        assert unealta.requires_confirmation is False


async def test_decizia_vine_cu_motivele_motorului() -> None:
    unealta = _tool("get_credit_decision")

    date = await unealta.callback(PRINCIPAL, {})

    assert date["found"] is True
    assert date["status"] == "respinsa"
    assert date["scor"] == 41
    assert "indatorare" in date["explicatie"]
    assert date["motive"][0]["cod"] == "dti_prea_mare"
    # Textul spune si ce urmeaza, ca modelul sa nu inventeze el pasul urmator.
    assert "depune alta" in date["ce_urmeaza"]


async def test_un_id_strain_nu_deschide_dosarul_altcuiva() -> None:
    """Filtrarea se face pe lista proprie, nu pe id-ul primit de la model."""
    unealta = _tool("get_credit_decision")

    date = await unealta.callback(PRINCIPAL, {"application_id": str(uuid4())})

    # Cade inapoi pe cererea proprie cea mai recenta, niciodata pe alta.
    assert date["found"] is True
    assert date["status"] == "respinsa"


async def test_urmatoarea_rata_o_sare_pe_cea_platita() -> None:
    date = await _tool("get_next_installment").callback(PRINCIPAL, {})

    assert len(date["installments"]) == 1
    assert date["installments"][0]["numar_rata"] == 2


async def test_simularea_merge_prin_motor_nu_prin_model() -> None:
    """Cifra trebuie sa fie chiar cea pe care ar da-o fluxul real de creditare."""
    from decimal import Decimal

    from app.credit import amortizare

    date = await _tool("simulate_credit").callback(PRINCIPAL, {"suma": "30000", "luni": 48})

    principal = amortizare.bani_din_lei(Decimal("30000"))
    asteptat = amortizare.lei_din_bani(
        amortizare.rata_lunara_bani(principal, Decimal("0.099"), 48)
    )
    assert date["rata_lunara"] == pytest.approx(float(asteptat))
    assert date["cost_total"] > 0


async def test_simularea_refuza_valori_absurde() -> None:
    unealta = _tool("simulate_credit")

    assert "error" in await unealta.callback(PRINCIPAL, {"suma": "-5", "luni": 12})
    assert "error" in await unealta.callback(PRINCIPAL, {"suma": "abc", "luni": 12})


def test_intentia_separa_dosarul_de_brosura() -> None:
    """Intrebarile despre dosarul propriu merg la agent, cele despre produs la RAG."""
    assert classify_intent("de ce mi-a fost respinsa cererea?") == "credit_question"
    assert classify_intent("ce rata am luna asta?") == "credit_question"
    assert classify_intent("ce se intampla cu creditul meu?") == "credit_question"

    # Astea raman intrebari de cunostinte — brosura, nu dosarul.
    assert classify_intent("Este o oferta buna la credit ipotecar?") == "unknown"
    assert classify_intent("ce comision are transferul?") == "document_question"

    # Si nu fura ce era deja rutat corect.
    assert classify_intent("cat am cheltuit luna asta?") == "spending_analysis"
    assert classify_intent("cat am in cont?") == "account_overview"
