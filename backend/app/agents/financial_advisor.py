"""Adaptor peste financial advisor-ul lui Cristi (agents/financiar.py).

Decizia (2026-08-20): pastram orchestratorul meu — persistenta conversatiilor,
compresia, atasamentele, vocea, nivelul de incredere (agents/base.py) — dar
"creierul" agentului financial_advisor devine bucla lui de tool-calling peste
AnalizaService (solduri, cashflow lunar, tranzactii, neregularitati/frauda),
nu tool-urile mele simple (get_accounts/get_spending_summary/run_scenario).

Diferenta fata de restul agentilor mei: acesta nu cheama chat_provider.complete()
o singura data — delegheaza intreaga tura catre AgentModel-ul lui Cristi
(app/agents/baza.py), care isi ruleaza propria bucla de tool-calling peste
azure-ai-inference. select_tools() intoarce mereu [] — executorul meu nu are
ce rula, tool-urile ruleaza in interiorul buclei lui, invizibile pentru mine.

Foloseste create_user_client (RLS pastrat), nu service_role: asa a fost gandit
stratul de repository-uri ale lui Cristi (vezi infrastructure/supabase.py).
Necesita deci Principal.access_token — cerere fara sesiune reala (ex. token
intern) primeste un raspuns clar, nu o eroare de autentificare confuza.
"""

from __future__ import annotations

from uuid import UUID

from app.agents import financiar
from app.agents.base import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    AgentAnswer,
    AttachmentContext,
)
from app.agents.registru import construieste_analiza
from app.agents.specs import FINANCIAL_ADVISOR
from app.context.builder import AssembledContext
from app.core.config import get_settings
from app.core.errors import AiProviderUnavailableError
from app.core.security import Principal
from app.infrastructure.llm import get_client_model
from app.infrastructure.supabase import create_user_client
from app.providers.base import ChatProvider
from app.tools.base import SelectedTool, ToolResult

_NO_SESSION_TEXT_RO = (
    "Analiza financiara detaliata are nevoie de sesiunea ta autentificata — "
    "reincearca din aplicatie, autentificat normal."
)


class FinancialAdvisorAgent:
    spec = FINANCIAL_ADVISOR

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        # Tool-urile lui Cristi (financiar_tools.py) ruleaza in bucla proprie
        # din AgentModel.executa — nu prin executorul meu de tool-uri.
        return []

    async def respond(
        self,
        principal: Principal,
        user_text: str,
        context: AssembledContext,
        tool_results: list[ToolResult],
        chat_provider: ChatProvider,
        attachments: list[AttachmentContext] = (),
    ) -> AgentAnswer:
        if not principal.access_token:
            return AgentAnswer(text=_NO_SESSION_TEXT_RO, confidence=None)

        settings = get_settings()
        if not settings.agenti_activi:
            raise AiProviderUnavailableError("Analiza financiara (AZURE_AI_*) nu este configurata.")

        client_supabase = create_user_client(settings, principal.access_token)
        analiza = construieste_analiza(client_supabase, settings)
        client_model = get_client_model()

        agent = financiar.construieste(client_model, settings, analiza, UUID(principal.user_id))
        rezultat = await agent.executa(user_text)

        confidence = CONFIDENCE_HIGH if rezultat.disponibil else CONFIDENCE_LOW
        return AgentAnswer(text=rezultat.raspuns, confidence=confidence)
