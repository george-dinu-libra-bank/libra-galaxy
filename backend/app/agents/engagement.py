from __future__ import annotations

from app.agents.base import AgentAnswer, AttachmentContext, build_system_prompt, build_user_message, confidence_from_tool_results
from app.agents.specs import ENGAGEMENT
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider
from app.tools.base import SelectedTool, ToolResult


class EngagementAgent:
    spec = ENGAGEMENT

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        return [SelectedTool("get_accounts", {}, "context minim pentru un ton potrivit")]

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
