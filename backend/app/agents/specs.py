"""Cei 5 agenti, declarati ca date (docs/AGENTS.md) — documentatie executabila.

Orchestratorul, verificarile de eligibilitate si (in viitor) dashboard-ul de
admin citesc acelasi obiect, ca specificatia sa nu se poata desincroniza de
comportament.
"""

from __future__ import annotations

from app.agents.base import AgentSpec
from app.tools.base import RiskLevel

FINANCIAL_ADVISOR = AgentSpec(
    agent_id="financial_advisor",
    purpose="Explica situatia financiara a utilizatorului si consecintele unor alegeri.",
    responsibilities=(
        "interpreteaza proiectii de scenariu deterministe",
        "analizeaza solduri si tendinte de cheltuieli",
    ),
    prohibited=(
        "sa calculeze el insusi solduri sau proiectii",
        "sa execute transferuri sau sa schimbe reguli de alocare",
    ),
    tool_names=frozenset({"get_accounts", "get_spending_summary", "run_scenario"}),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="advisor-v0",
    intents=("account_overview", "what_if", "financial_advice"),
)

TRANSACTION_INTELLIGENCE = AgentSpec(
    agent_id="transaction_intelligence",
    purpose="Transforma tranzactiile brute in intelesuri structurate si explicabile.",
    responsibilities=("explica tipare de cheltuieli calculate determinist",),
    prohibited=("sa calculeze el insusi totaluri de cheltuieli",),
    tool_names=frozenset({"get_accounts", "get_recent_transactions", "get_spending_summary"}),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="transactions-v0",
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
