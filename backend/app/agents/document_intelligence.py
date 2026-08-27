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

_ATTACHMENT_ONLY_RULE_RO = (
    "Utilizatorul a trimis un atasament (poza sau document) fara nicio intrebare. Descrie pe scurt "
    "ce contine, apoi sugereaza explicit ce poti face cu el: sa verifici carei categorii de cheltuiala "
    "ii corespunde, sau sa il legi de o tranzactie reala din istoric daca utilizatorul confirma suma si "
    "data platii. NU afirma ca ai facut deja legatura sau ca ai categorisit ceva — doar sugereaza pasul "
    "urmator si intreaba daca utilizatorul vrea sa continue."
)
_ATTACHMENT_ONLY_RULE_EN = (
    "The user sent an attachment (photo or document) without asking anything. Briefly describe what "
    "it contains, then explicitly suggest what you can do with it: check which spending category it "
    "matches, or link it to a real transaction from their history if they confirm the amount and date. "
    "Do NOT claim you have already linked or categorized anything — just suggest the next step and ask "
    "if they want to proceed."
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
        # Categoria = folderul din galaxy-bank-knowledge (migratia 0033).
        # Ingustare aplicata doar unde intentia chiar garanteaza subiectul —
        # credit_intent e eticheta care garanteaza cel mai clar subiectul, chiar
        # daca ajunge aici (nu la credit_advisor) pentru partea informativa.
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

        citations = [
            {"document_id": hit["document_id"], "section": hit.get("section"), "score": hit["score"]}
            for hit in hits[:3]
        ]
        confidence = _confidence_from_score(hits[0]["score"]) if hits else CONFIDENCE_MEDIUM

        if not user_text.strip() and attachments:
            # Atasament trimis singur, fara intrebare — nu are sens sa cerem
            # citare stricta din fragmente RAG (n-a fost cautat nimic relevant,
            # vezi search_bank_knowledge cu query gol); modelul trebuie doar sa
            # descrie atasamentul si sa sugereze pasul urmator.
            grounding_rule = _ATTACHMENT_ONLY_RULE_RO if principal.locale == "ro" else _ATTACHMENT_ONLY_RULE_EN
        elif hits:
            grounding_rule = "Raspunde EXCLUSIV din fragmentele regasite de mai sus si din fisierul atasat, daca exista."
        elif attachments:
            grounding_rule = "Nu exista fragmente din baza de cunostinte — raspunde EXCLUSIV din fisierul atasat de utilizator."
        else:
            # Nici fragmente, nici atasament — inainte se scurtcircuita aici cu
            # un text fix; acum modelul insusi hotaraste, ghidat de regula de
            # refuz off-topic de mai jos (comuna tuturor agentilor) sau, daca
            # intrebarea chiar e bancara dar nedocumentata, o spune sincer.
            grounding_rule = (
                "Nu exista fragmente din baza de cunostinte pentru aceasta intrebare. Daca intrebarea "
                "e despre domeniul bancar dar informatia nu exista, spune sincer ca nu e documentata. "
                "Daca nu are nicio legatura cu domeniul bancar, aplica mai jos regula despre refuzul politicos."
            )

        system_prompt = build_system_prompt(self.spec, context) + (
            f"\n\n{grounding_rule} Daca informatia nu e acolo, spune simplu ca nu e documentata — "
            f"fara sa mentionezi ce titlu de sectiune sau ce document ai gasit in schimb.\n"
            f"INAINTE de toate: daca intrebarea utilizatorului nu are nicio legatura cu domeniul "
            f"bancar (Galaxy Bank, conturi, carduri, tranzactii, credite, transferuri, produse "
            f"bancare) — de exemplu o gluma, o curiozitate generala, orice subiect fara legatura cu "
            f"banii sau banca — raspunzi simplu ca poti ajuta doar cu intrebari despre domeniul "
            f"bancar. Asta se aplica INDIFERENT de fragmentele regasite mai sus: un fragment poate "
            f"contine cuvinte in comun cu intrebarea (ex. 'bani') fara sa fie relevant pentru ce s-a "
            f"cerut de fapt — nu forta un raspuns dintr-un fragment doar pentru ca a fost regasit."
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
