"""Rutabil, fara tool-uri (docs/AGENTS.md #3) — nu exista inca date/servicii KYC deterministe
in spatele lui, deci raspunde onest ca nu poate ajuta, in loc sa simuleze o capabilitate.

Raspunsul vine din model (ca la ceilalti agenti), nu dintr-un text fix — dar
`spec.prohibited` (agents/specs.py) ii interzice deja sa aprobe/decida ceva, deci
onestitatea ramane garantata de prompt, nu de un string static."""

from __future__ import annotations

from app.agents.base import AgentAnswer, AttachmentContext, build_system_prompt, build_user_message, confidence_from_tool_results
from app.agents.specs import COMPLIANCE_KYC
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider
from app.tools.base import SelectedTool, ToolResult


class ComplianceKycAgent:
    spec = COMPLIANCE_KYC

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
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
        system_prompt = build_system_prompt(self.spec, context) + (
            "\n\nNu exista inca niciun tool/serviciu KYC in spatele tau. Spune sincer, in cateva "
            "cuvinte, ca fluxul de identificare a clientului (KYC) nu are inca un instrument dedicat "
            "in asistent, si indruma utilizatorul spre sectiunea de suport din aplicatie pentru "
            "verificari sau documente."
        )
        completion = await chat_provider.complete(
            [ChatMessage(role="system", content=system_prompt), build_user_message(user_text, attachments)]
        )
        return AgentAnswer(
            text=completion.text, citations=[], confidence=confidence_from_tool_results(tool_results),
            tokens_in=completion.tokens_in, tokens_out=completion.tokens_out, tokens_cached=completion.tokens_cached,
        )
