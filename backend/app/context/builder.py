"""Un singur ContextBuilder pentru toti agentii (docs/AI_ARCHITECTURE.md #5).

Fiecare sectiune e etichetata cu sursa si cu is_authoritative, bugetata
independent, si ordinea e fixa — o conversatie lunga nu poate inlocui
soldurile. Trunchierile se inregistreaza, niciodata nu se pierd tacut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContextSource(str, Enum):
    IDENTITY = "identity"
    CONVERSATION_SUMMARY = "conversation_summary"
    USER_MEMORY = "user_memory"
    RECENT_CONVERSATION = "recent_conversation"
    RETRIEVED_KNOWLEDGE = "retrieved_knowledge"
    BANKING_STATE = "banking_state"
    TOOL_RESULT = "tool_result"


_AUTHORITATIVE_SOURCES = {ContextSource.BANKING_STATE, ContextSource.TOOL_RESULT}

_BUDGETS: dict[ContextSource, int] = {
    ContextSource.IDENTITY: 500,
    ContextSource.CONVERSATION_SUMMARY: 3_000,
    ContextSource.USER_MEMORY: 2_000,
    ContextSource.RECENT_CONVERSATION: 6_000,
    ContextSource.RETRIEVED_KNOWLEDGE: 7_000,
    ContextSource.BANKING_STATE: 6_000,
    ContextSource.TOOL_RESULT: 5_000,
}


@dataclass(frozen=True)
class ContextSection:
    source: ContextSource
    title: str
    text: str
    is_authoritative: bool
    truncated: bool = False


@dataclass(frozen=True)
class AssembledContext:
    sections: list[ContextSection]
    truncated_sections: list[str]

    def render(self) -> str:
        blocks = []
        for section in self.sections:
            if not section.text.strip():
                continue
            label = "authoritative" if section.is_authoritative else "recollection"
            blocks.append(f"## {section.title}\n[source={section.source.value} authority={label}]\n{section.text}")
        return "\n\n---\n\n".join(blocks)


class ContextBuilder:
    def add(self, source: ContextSource, title: str, text: str) -> ContextSection:
        budget = _BUDGETS[source]
        truncated = len(text) > budget
        clamped = text[:budget]
        return ContextSection(
            source=source, title=title, text=clamped, is_authoritative=source in _AUTHORITATIVE_SOURCES, truncated=truncated
        )

    def build(self, sections: list[ContextSection]) -> AssembledContext:
        truncated = [section.title for section in sections if section.truncated]
        return AssembledContext(sections=sections, truncated_sections=truncated)
