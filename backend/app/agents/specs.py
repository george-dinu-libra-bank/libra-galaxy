"""Cei 5 agenti, declarati ca date (docs/AGENTS.md) — documentatie executabila.

Orchestratorul, verificarile de eligibilitate si (in viitor) dashboard-ul de
admin citesc acelasi obiect, ca specificatia sa nu se poata desincroniza de
comportament.
"""

from __future__ import annotations

from app.agents.base import AgentSpec
from app.tools.base import RiskLevel

# "Creierul" acestui agent e delegat catre agents/financiar.py (Cristi): o bucla
# proprie de tool-calling peste AnalizaService (sold, cashflow lunar, tranzactii,
# neregularitati), nu tool-urile registrului meu de mai jos — vezi
# agents/financial_advisor.py. tool_names ramane gol intentionat: eligibility.py
# nu are ce sa verifice, pentru ca acest agent nu cere niciun tool prin
# ToolRegistry (select_tools() intoarce mereu []).
FINANCIAL_ADVISOR = AgentSpec(
    agent_id="financial_advisor",
    purpose="Explica situatia financiara a utilizatorului: solduri, cashflow lunar, tranzactii, neregularitati.",
    responsibilities=(
        "analizeaza solduri si cashflow lunar prin tool-uri proprii (agents/financiar.py)",
        "semnaleaza plati care ies din tiparul obisnuit, ca observatii statistice",
    ),
    prohibited=(
        "sa calculeze el insusi solduri, cashflow sau proiectii",
        "sa execute transferuri, sa blocheze carduri sau sa schimbe reguli de alocare",
        "sa prezinte o neregularitate statistica drept frauda confirmata",
    ),
    tool_names=frozenset(),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="advisor-v1-cristi",
    intents=("account_overview", "what_if", "financial_advice"),
)

TRANSACTION_INTELLIGENCE = AgentSpec(
    agent_id="transaction_intelligence",
    purpose="Transforma tranzactiile brute in intelesuri structurate si explicabile.",
    responsibilities=("explica tipare de cheltuieli calculate determinist",),
    prohibited=(
        "sa calculeze el insusi totaluri de cheltuieli",
        "sa inventeze formate de export (CSV/XLSX/JSON) sau optiuni de ales care nu exista",
        "sa mentioneze catre utilizator nume de campuri interne (id-uri, chei tehnice de tool-uri)",
    ),
    tool_names=frozenset({"get_accounts", "get_recent_transactions", "get_spending_summary"}),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="transactions-v1",
    intents=("spending_analysis",),
)

DOCUMENT_INTELLIGENCE = AgentSpec(
    agent_id="document_intelligence",
    purpose="Raspunde la intrebari despre politici, produse si proceduri, cu citare.",
    responsibilities=("raspunde exclusiv din continut regasit, cu citare a sursei",),
    prohibited=(
        "sa raspunda la intrebari de sold, proprietate sau stare de plata din regasire",
        "sa prezinte o afirmatie neregasita ca fapt citat",
    ),
    tool_names=frozenset({"search_bank_knowledge"}),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="documents-v0",
    intents=("document_question", "knowledge_question", "unknown"),
)

ENGAGEMENT = AgentSpec(
    agent_id="engagement",
    purpose="Formuleaza pe un ton potrivit informatii deja calculate determinist.",
    responsibilities=("adapteaza tonul si concizia la context",),
    prohibited=("sa inventeze un insight pe care niciun serviciu nu l-a produs",),
    tool_names=frozenset({"get_accounts"}),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="engagement-v0",
    intents=("engagement",),
)

COMPLIANCE_KYC = AgentSpec(
    agent_id="compliance_kyc",
    purpose="Asista un flux KYC decis determinist sau de un om.",
    responsibilities=("semnaleaza date lipsa sau inconsistente, cand exista tool-uri pentru asta",),
    prohibited=("sa aprobe sau sa respinga un caz", "sa decida un rating de risc"),
    tool_names=frozenset(),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="compliance-v0",
    intents=("kyc_workflow",),
)

ALL_AGENT_SPECS: tuple[AgentSpec, ...] = (
    FINANCIAL_ADVISOR,
    TRANSACTION_INTELLIGENCE,
    DOCUMENT_INTELLIGENCE,
    ENGAGEMENT,
    COMPLIANCE_KYC,
)
