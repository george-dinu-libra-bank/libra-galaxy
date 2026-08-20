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


@dataclass(frozen=True)
class ChatCompletion:
    text: str
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    deployment: str


class ChatProvider(Protocol):
    """`temperature` nu e parametru aici: gpt-5-mini (model de reasoning) accepta
    doar valoarea implicita si respinge orice altceva cu 400 (verificat live)."""

    deployment: str

    async def complete(self, messages: list[ChatMessage]) -> ChatCompletion: ...


class EmbeddingProvider(Protocol):
    deployment: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class VoiceProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, content_type: str, locale: str) -> str: ...

    async def synthesize(self, text: str, locale: str) -> bytes: ...
