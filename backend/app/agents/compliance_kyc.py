"""Rutabil, fara tool-uri (docs/AGENTS.md #3) — nu exista inca date/servicii KYC deterministe
in spatele lui, deci raspunde onest ca nu poate ajuta, in loc sa simuleze o capabilitate."""

from __future__ import annotations

from app.agents.base import AgentAnswer, AttachmentContext
from app.agents.specs import COMPLIANCE_KYC
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatProvider
from app.tools.base import SelectedTool, ToolResult

_NOT_AVAILABLE_TEXT_RO = (
    "Fluxul de identificare a clientului (KYC) nu are inca un instrument dedicat in asistent. "
    "Pentru verificari sau documente, foloseste sectiunea de suport din aplicatie."
)


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
        return AgentAnswer(text=_NOT_AVAILABLE_TEXT_RO, citations=[])
