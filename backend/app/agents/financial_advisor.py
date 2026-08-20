from __future__ import annotations

import re

from app.agents.base import AgentAnswer, AttachmentContext, build_system_prompt, build_user_message, confidence_from_tool_results
from app.agents.specs import FINANCIAL_ADVISOR
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider
from app.tools.base import SelectedTool, ToolResult

_AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_MONTHS_RE = re.compile(r"(\d+)\s*(luni|lun[aă]|months?)")


def _extract_scenario_args(user_text: str) -> dict:
    amounts = _AMOUNT_RE.findall(user_text)
    monthly_amount = float(amounts[0].replace(",", ".")) if amounts else 500.0

    months_match = _MONTHS_RE.search(user_text.lower())
    months = int(months_match.group(1)) if months_match else 12

    return {"monthly_amount": monthly_amount, "months": months}


class FinancialAdvisorAgent:
    spec = FINANCIAL_ADVISOR

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        selections = [SelectedTool("get_accounts", {}, "solduri deschise, necesare pentru orice explicatie")]

        if intent == "what_if":
            selections.append(
                SelectedTool("run_scenario", _extract_scenario_args(user_text), "intrebare de tip what-if")
            )
        else:
            selections.append(
                SelectedTool("get_spending_summary", {"days": 30}, "context de cheltuieli pentru o privire de ansamblu")
            )

        return selections

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
