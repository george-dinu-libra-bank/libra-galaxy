"""Drumul de la o notificare de blocare pana la un raspuns care chiar explica.

Un om caruia i s-a blocat contul apasa "Intreaba asistentul" si ajunge aici cu
intrebarea scrisa. Daca intentia nu e recunoscuta, sau daca agentului nu i se
dau mesajele bancii, raspunsul e o generalitate politicoasa — exact cand omul
are nevoie de un fapt.
"""

import pytest

from app.agents.specs import TRANSACTION_INTELLIGENCE
from app.agents.transaction_intelligence import TransactionIntelligenceAgent
from app.orchestration.intent import classify_intent
from app.orchestration.routing import AgentRouter


@pytest.mark.parametrize(
    "intrebare",
    [
        "De ce mi-a fost blocat contul și ce trebuie să fac ca să-l deblochez?",
        "Contul meu a fost deblocat — ce s-a întâmplat și ce urmează?",
        "de ce nu pot plati cu cardul?",
        "nu pot face transfer, de ce?",
        "why is my account blocked",
        "cardul meu e blocat",
    ],
)
def test_intrebarile_despre_blocare_sunt_recunoscute(intrebare: str) -> None:
    assert classify_intent(intrebare) == "cont_blocat"


@pytest.mark.parametrize(
    ("intrebare", "asteptat"),
    [
        ("cat am cheltuit luna asta", "spending_analysis"),
        ("ce carduri am", "card_question"),
    ],
)
def test_intentia_noua_nu_le_fura_pe_celelalte(intrebare: str, asteptat: str) -> None:
    """„blocat" apare si in intrebari despre carduri; ordinea din tabel conteaza."""
    assert classify_intent(intrebare) == asteptat


def test_intrebarea_ajunge_la_agentul_potrivit() -> None:
    assert AgentRouter().select("cont_blocat") == "transaction_intelligence"


def test_agentul_cere_mesajele_bancii_nu_doar_starea_conturilor() -> None:
    """`get_accounts` spune CA e blocat; motivul e in mesajul scris de analist."""
    unelte = [
        t.name
        for t in TransactionIntelligenceAgent().select_tools("de ce e blocat contul", "cont_blocat")
    ]

    assert "get_bank_messages" in unelte
    assert "get_accounts" in unelte


def test_uneltele_cerute_sunt_si_declarate_in_spec() -> None:
    """Un tool cerut dar nedeclarat e refuzat la executie — vezi docs/AGENTS.md."""
    cerute = {
        t.name
        for t in TransactionIntelligenceAgent().select_tools("de ce e blocat contul", "cont_blocat")
    }

    assert cerute <= TRANSACTION_INTELLIGENCE.tool_names
