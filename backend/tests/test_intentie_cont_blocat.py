"""Drumul de la o notificare de blocare pana la un raspuns care chiar explica.

Un om caruia i s-a blocat contul apasa „Intreaba asistentul" si ajunge aici cu
intrebarea scrisa. Daca intentia nu ajunge la agentul potrivit, sau daca
agentului nu i se dau mesajele bancii, raspunsul e o generalitate politicoasa —
exact cand omul are nevoie de un fapt.

Testele astea verificau initial tabela de fraze din `orchestration/intent.py`,
stearsa intre timp: rutarea o face acum un model (`orchestration/llm_router.py`),
iar vocabularul de intentii se construieste din `spec.intents`. Nu se mai poate
verifica in test ce eticheta alege modelul pentru o propozitie anume — dar se
poate verifica exact ce l-a facut pe cel vechi sa functioneze: ca eticheta
exista in vocabular, ca duce la agentul potrivit, si ca agentul stie ce sa faca
la primirea ei. Aceea e veriga care s-ar rupe in tacere la un refactor.
"""

from app.agents.specs import ALL_AGENT_SPECS, TRANSACTION_INTELLIGENCE
from app.agents.transaction_intelligence import TransactionIntelligenceAgent

INTENTIA = "cont_blocat"


def test_eticheta_exista_in_vocabularul_routerului() -> None:
    """`llm_router.INTENT_LABELS` se compune din intentiile tuturor specificatiilor.

    Daca eticheta dispare de acolo, modelul nu o mai poate alege — schema lui de
    iesire o respinge — si intrebarea „de ce mi-a fost blocat contul" cade pe o
    intentie generica, unde agentul nu mai cere mesajele bancii.
    """
    from app.orchestration.llm_router import INTENT_LABELS

    assert INTENTIA in INTENT_LABELS


def test_eticheta_apartine_unui_singur_agent() -> None:
    """Doi agenti cu aceeasi eticheta ar face rutarea ambigua."""
    detinatori = [spec.agent_id for spec in ALL_AGENT_SPECS if INTENTIA in spec.intents]

    assert detinatori == [TRANSACTION_INTELLIGENCE.agent_id]


def test_agentul_cere_mesajele_bancii_nu_doar_starea_conturilor() -> None:
    """`get_accounts` spune CA e blocat; motivul e in mesajul scris de analist."""
    unelte = [
        t.name
        for t in TransactionIntelligenceAgent().select_tools("de ce e blocat contul", INTENTIA)
    ]

    assert "get_bank_messages" in unelte
    assert "get_accounts" in unelte


def test_uneltele_cerute_sunt_si_declarate_in_spec() -> None:
    """Un tool cerut dar nedeclarat e refuzat la executie — vezi docs/AGENTS.md."""
    cerute = {
        t.name
        for t in TransactionIntelligenceAgent().select_tools("de ce e blocat contul", INTENTIA)
    }

    assert cerute <= TRANSACTION_INTELLIGENCE.tool_names
