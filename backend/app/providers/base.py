from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Union


@dataclass(frozen=True)
class ImagePart:
    """O poza atașata, trimisa direct modelului de chat — nu exista un VisionProvider
    separat (CLAUDE.md #16): folosim doar capacitatea multimodala a modelului de chat existent."""

    data_uri: str


ChatContent = Union[str, list[Union[str, ImagePart]]]


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: ChatContent
    # Numai pentru role="tool": raspunsul se leaga de apelul care l-a cerut.
    tool_call_id: str | None = None
    # Numai pentru role="assistant", cand tura precedenta a cerut tool-uri.
    # Se trimite inapoi neschimbat, ca modelul sa-si vada propriile apeluri.
    tool_calls: tuple["ApelTool", ...] = ()


@dataclass(frozen=True)
class ApelTool:
    """Un tool cerut de model, cu argumentele compuse de el."""

    id: str
    nume: str
    argumente: dict


@dataclass(frozen=True)
class ChatCompletion:
    text: str
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    deployment: str
    # Gol cand modelul a raspuns direct. Cand nu e gol, raspunsul inca nu e
    # gata: apelantul executa tool-urile si il intreaba din nou.
    apeluri: tuple[ApelTool, ...] = ()


class ChatProvider(Protocol):
    """`temperature` nu e parametru aici: gpt-5-mini (model de reasoning) accepta
    doar valoarea implicita si respinge orice altceva cu 400 (verificat live)."""

    deployment: str

    async def complete(
        self, messages: list[ChatMessage], tools: list[dict] | None = None
    ) -> ChatCompletion:
        """`tools` in forma OpenAI. Optional: agentii care nu-l dau se comporta
        exact ca inainte, iar modelul nu are ce cere."""
        ...


@dataclass(frozen=True)
class StructuredCompletion:
    """Ca ChatCompletion, dar `data` e deja JSON validat contra schemei cerute —
    apelantul nu mai face `json.loads` si nu mai verifica singur campurile."""

    data: dict
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    deployment: str


class StructuredChatProvider(Protocol):
    """Iesire structurata, pentru cod care are nevoie de campuri, nu de proza —
    pipeline-ul AI de credite (app/credit/ai/), niciodata agentii conversationali
    din app/agents/, care raman pe ChatProvider simplu.

    Verificat live (2026-08-24) ca deployment-ul `gpt-5-mini` din Foundry accepta
    `response_format={"type": "json_schema", "strict": true}`: raspunde cu JSON
    valid, fara sa se abata de la schema."""

    deployment: str

    async def complete_json(
        self, messages: list[ChatMessage], schema_name: str, schema: dict
    ) -> StructuredCompletion: ...


class EmbeddingProvider(Protocol):
    deployment: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class VoiceProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, content_type: str, locale: str) -> str: ...

    async def synthesize(self, text: str, locale: str) -> bytes: ...
