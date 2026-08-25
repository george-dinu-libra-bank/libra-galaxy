"""Agentul care trebuie sa citeze o sursa pentru orice afirmatie — de aceea e ruta implicita
pentru intentii neclasificate (docs/AGENTS.md #4).

Citarea ramane in `citations` (structurat, pentru audit/telemetrie), dar textul
vazut de utilizator nu mai mentioneaza sursa — doar un nivel de incredere,
calculat determinist din scorul de regasire, nu inventat de model.
"""

from __future__ import annotations

from app.agents.base import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    AgentAnswer,
    AttachmentContext,
    build_system_prompt,
    build_user_message,
)
from app.agents.specs import DOCUMENT_INTELLIGENCE
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider
from app.tools.base import SelectedTool, ToolResult

_NO_MATCH_TEXT_RO = (
    "Îmi pare rău, nu pot răspunde la această întrebare. Te rog reformuleaz-o sau "
    "contactează echipa de suport pentru ajutor."
)

_SCORE_HIGH_THRESHOLD = 0.65
_SCORE_MEDIUM_THRESHOLD = 0.5


def _confidence_from_score(top_score: float) -> str:
    if top_score >= _SCORE_HIGH_THRESHOLD:
        return CONFIDENCE_HIGH
    if top_score >= _SCORE_MEDIUM_THRESHOLD:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


class DocumentIntelligenceAgent:
    spec = DOCUMENT_INTELLIGENCE

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        # Categoria = folderul din galaxy-bank-knowledge (migratia 0027).
        # Ingustare aplicata doar unde intentia chiar garanteaza subiectul —
        # credit_intent e singura care ajunge aici prin fallback-ul router-ului
        # (routing.py::DEFAULT_AGENT_ID) fara sa fie o intrebare generica.
        # document_question/knowledge_question/unknown raman fara filtru:
        # pot fi despre orice categorie (ex. comisioane apar si la carduri,
        # si la conturi, si la transferuri).
        args = {"query": user_text}
        if intent == "credit_intent":
            args["categorie_hint"] = "credite"
        return [SelectedTool("search_bank_knowledge", args, "raspuns bazat pe cunoastere, nu pe memorie")]

    async def respond(
        self,
        principal: Principal,
        user_text: str,
        context: AssembledContext,
        tool_results: list[ToolResult],
        chat_provider: ChatProvider,
        attachments: list[AttachmentContext] = (),
    ) -> AgentAnswer:
        hits = self._hits(tool_results)

        if not hits and not attachments:
            return AgentAnswer(text=_NO_MATCH_TEXT_RO, citations=[])

        citations = [
            {"document_id": hit["document_id"], "section": hit.get("section"), "score": hit["score"]}
            for hit in hits[:3]
        ]
        confidence = _confidence_from_score(hits[0]["score"]) if hits else CONFIDENCE_MEDIUM

        if hits:
            grounding_rule = "Raspunde EXCLUSIV din fragmentele regasite de mai sus si din fisierul atasat, daca exista."
        else:
            grounding_rule = "Nu exista fragmente din baza de cunostinte — raspunde EXCLUSIV din fisierul atasat de utilizator."

        system_prompt = build_system_prompt(self.spec, context) + (
            f"\n\n{grounding_rule} Daca informatia nu e acolo, spune simplu ca nu e documentata — "
            f"fara sa mentionezi ce titlu de sectiune sau ce document ai gasit in schimb."
        )
        completion = await chat_provider.complete(
            [ChatMessage(role="system", content=system_prompt), build_user_message(user_text, attachments)]
        )
        return AgentAnswer(
            text=completion.text, citations=citations, confidence=confidence,
            tokens_in=completion.tokens_in, tokens_out=completion.tokens_out, tokens_cached=completion.tokens_cached,
        )

    @staticmethod
    def _hits(tool_results: list[ToolResult]) -> list[dict]:
        for result in tool_results:
            if result.tool_name == "search_bank_knowledge" and result.success and result.data:
                return result.data.get("hits", [])
        return []
