"""Rutare determinista intentie -> agent (docs/AGENTS.md #4)."""

from __future__ import annotations

from app.agents.specs import ALL_AGENT_SPECS

DEFAULT_AGENT_ID = "document_intelligence"


class AgentRouter:
    def __init__(self) -> None:
        self._by_intent: dict[str, str] = {}
        for spec in ALL_AGENT_SPECS:
            for intent in spec.intents:
                self._by_intent[intent] = spec.agent_id

    def select(self, intent: str) -> str:
        return self._by_intent.get(intent, DEFAULT_AGENT_ID)
