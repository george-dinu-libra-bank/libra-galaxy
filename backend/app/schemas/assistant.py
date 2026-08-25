from __future__ import annotations

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    conversation_id: str | None = Field(default=None, description="Omite pentru o conversatie noua.")
    text: str = Field(min_length=1, max_length=4000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=5)
    tts: bool = Field(default=False, description="Daca e adevarat, raspunsul vine si ca audio (sinteza vocala).")


class CitationOut(BaseModel):
    document_id: str
    section: str | None
    score: float


class GeneratedFileOut(BaseModel):
    url: str
    filename: str
    kind: str = "pdf"


class QuickActionAccountOut(BaseModel):
    id: str
    name: str | None
    iban: str
    currency: str | None


class QuickActionOut(BaseModel):
    kind: str
    accounts: list[QuickActionAccountOut] = Field(default_factory=list)
    url: str


class SendMessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    text: str
    citations: list[CitationOut]
    confidence: str | None = None
    agent_id: str
    file: GeneratedFileOut | None = None
    quick_action: QuickActionOut | None = None
    audio_base64: str | None = None


class VoiceMessageResponse(SendMessageResponse):
    pass


class ConversationOut(BaseModel):
    id: str
    title: str
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    text: str
    citations: list[CitationOut]
    confidence: str | None = None
    channel: str
    created_at: str
    file: GeneratedFileOut | None = None
    quick_action: QuickActionOut | None = None


class AgentCapabilityOut(BaseModel):
    agent_id: str
    purpose: str
    tools: list[str]


class CapabilitiesResponse(BaseModel):
    agents: list[AgentCapabilityOut]


class AttachmentOut(BaseModel):
    id: str
    kind: str
    filename: str
    size_bytes: int
