from __future__ import annotations

from app.agents.base import AgentAnswer, AttachmentContext, build_system_prompt, build_user_message, confidence_from_tool_results
from app.agents.specs import TRANSACTION_INTELLIGENCE
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider
from app.tools.base import SelectedTool, ToolResult
from app.tools.categorii_tranzactii import extrage_suma


class TransactionIntelligenceAgent:
    spec = TRANSACTION_INTELLIGENCE

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        if intent == "card_question":
            return [
                SelectedTool("get_cards", {}, "detalii despre cardurile proprii"),
                SelectedTool("get_accounts", {}, "cardurile nu au sold propriu, banii sunt in conturi"),
            ]
        if intent == "categorize_receipt_intent":
            # Suma extrasa determinist din text — la fel ca la credit_advisor,
            # nu lasam modelul sa umple argumentul tool-ului. Fara o suma
            # gasita, tool-ul intoarce candidates=[] si modelul (ghidat de
            # prohibited din specs.py) trebuie sa ceara suma explicit.
            suma = extrage_suma(user_text)
            return [
                SelectedTool(
                    "find_transaction_for_receipt", {"suma": suma} if suma is not None else {},
                    "utilizatorul vrea sa lege un atasament de o plata reala",
                ),
            ]
        return [
            SelectedTool("get_recent_transactions", {"limit": 30}, "tranzactii recente pentru analiza"),
            SelectedTool("get_spending_summary", {"days": 30}, "rezumat de cheltuieli pentru context"),
        ]

    async def respond(
        self,
        principal: Principal,
        user_text: str,
        context: AssembledContext,
        tool_results: list[ToolResult],
        chat_provider: ChatProvider,
        attachments: list[AttachmentContext] = (),
    ) -> AgentAnswer:
        system_prompt = build_system_prompt(self.spec, context)
        completion = await chat_provider.complete(
            [ChatMessage(role="system", content=system_prompt), build_user_message(user_text, attachments)]
        )
        return AgentAnswer(
            text=completion.text, citations=[], confidence=confidence_from_tool_results(tool_results),
            tokens_in=completion.tokens_in, tokens_out=completion.tokens_out, tokens_cached=completion.tokens_cached,
        )
