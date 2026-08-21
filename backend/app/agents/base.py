"""Contractul unui agent (docs/AGENTS.md) — nu se apeleaza intre ei, nu depasesc tool-urile declarate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider, ImagePart
from app.tools.base import RiskLevel, SelectedTool, ToolResult

MAX_ATTACHMENT_TEXT_CHARS = 6_000


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    purpose: str
    responsibilities: tuple[str, ...]
    prohibited: tuple[str, ...]
    tool_names: frozenset[str]
    risk_ceiling: RiskLevel
    prompt_version: str
    intents: tuple[str, ...]


CONFIDENCE_HIGH = "ridicat"
CONFIDENCE_MEDIUM = "mediu"
CONFIDENCE_LOW = "scazut"


@dataclass(frozen=True)
class AgentAnswer:
    text: str
    citations: list[dict] = field(default_factory=list)
    confidence: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0


@dataclass(frozen=True)
class AttachmentContext:
    """Un atasament pregatit pentru model — text deja extras (PDF) sau imagine
    trimisa direct modelului multimodal de chat (fara VisionProvider, CLAUDE.md #16)."""

    kind: str  # "pdf" | "imagine"
    filename: str
    extracted_text: str | None = None
    image_data_uri: str | None = None


class Agent(Protocol):
    spec: AgentSpec

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]: ...

    async def respond(
        self,
        principal: Principal,
        user_text: str,
        context: AssembledContext,
        tool_results: list[ToolResult],
        chat_provider: ChatProvider,
        attachments: list[AttachmentContext] = (),
    ) -> AgentAnswer: ...


def build_system_prompt(spec: AgentSpec, context: AssembledContext) -> str:
    """Prompt de baza comun tuturor agentilor: scop, interdictii explicite, apoi contextul asamblat."""
    prohibited = "\n".join(f"- NU {item}." for item in spec.prohibited)
    return (
        f"Esti agentul '{spec.agent_id}' din Galaxy Bank. Scop: {spec.purpose}\n"
        f"Raspunzi in limba utilizatorului (ro/en), cu aceleasi cifre in ambele limbi.\n"
        f"Nu afirmi niciodata ca o actiune a reusit decat daca un tool a confirmat asta.\n"
        f"Nu mentiona in raspuns numele tool-urilor, ID-uri de documente sau cuvinte precum "
        f"'sursa:'/'conform datelor din'/'get_...' — utilizatorul vede doar continutul, "
        f"niciodata mecanismul intern prin care a fost obtinut (nivelul de incredere e "
        f"calculat separat, determinist, nu de tine).\n"
        f"{prohibited}\n\n{context.render()}"
    )


def confidence_from_tool_results(tool_results: list[ToolResult]) -> str | None:
    """Nivel de incredere calculat determinist din rezultatele tool-urilor, nu inventat de model —
    grounded in date reale (succes) e mereu 'ridicat', partial 'mediu', fara date deloc 'scazut'."""
    if not tool_results:
        return None

    successes = sum(1 for result in tool_results if result.success)
    if successes == len(tool_results):
        return CONFIDENCE_HIGH
    if successes > 0:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def build_user_message(user_text: str, attachments: list[AttachmentContext] = ()) -> ChatMessage:
    """Compune mesajul utilizatorului, cu poze ca parti multimodale si text de PDF inline."""
    if not attachments:
        return ChatMessage(role="user", content=user_text)

    parts: list[str | ImagePart] = [user_text]
    for attachment in attachments:
        if attachment.kind == "imagine" and attachment.image_data_uri:
            parts.append(ImagePart(data_uri=attachment.image_data_uri))
        elif attachment.extracted_text:
            snippet = attachment.extracted_text[:MAX_ATTACHMENT_TEXT_CHARS]
            parts.append(f"\n\n[Continut din fisierul atasat „{attachment.filename}”]\n{snippet}")

    return ChatMessage(role="user", content=parts)
