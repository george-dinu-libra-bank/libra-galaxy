"""Compresie determinista, incrementala pe `summary_watermark` (docs/AI_ARCHITECTURE.md #6).

Spre deosebire de referinta (care recitea toate mesajele si rescria rezumatul
la fiecare tura), aici doar mesajele dintre watermark si noul prag de foldare
sunt citite si condensate — costul per tura ramane constant, nu creste cu
lungimea conversatiei.
"""

from __future__ import annotations

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import Message, MessageRepository
from app.repositories.summary_repository import SummaryRepository

RECENT_WINDOW = 12
MAX_SUMMARY_CHARS = 4_000
MESSAGE_PREVIEW_CHARS = 240


def preview(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def condense_message(message: Message) -> str:
    role = "UTILIZATOR" if message.role == "user" else "ASISTENT"
    return f"{role}: {preview(message.text, MESSAGE_PREVIEW_CHARS)}"


def fold_messages_into_summary(existing_summary: str, new_messages: list[Message], max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """Functie pura: adauga liniile noi la rezumatul existent si taie la limita."""
    if not new_messages:
        return existing_summary

    new_lines = "\n".join(condense_message(message) for message in new_messages)
    combined = f"{existing_summary}\n{new_lines}".strip() if existing_summary else new_lines
    return combined[-max_chars:]


async def compress_conversation(
    conversation_id: str,
    user_id: str,
    watermark: int,
    conversation_repository: ConversationRepository,
    message_repository: MessageRepository,
    summary_repository: SummaryRepository,
    window: int = RECENT_WINDOW,
) -> None:
    total = await message_repository.count(conversation_id)
    fold_end = total - window

    if fold_end <= watermark:
        return

    new_messages = await message_repository.range(conversation_id, watermark + 1, fold_end)
    if not new_messages:
        return

    current_summary = await summary_repository.get(conversation_id)
    updated_text = fold_messages_into_summary(current_summary.text, new_messages)

    await summary_repository.upsert(conversation_id, user_id, updated_text, fold_end)
    await conversation_repository.update_watermark(conversation_id, fold_end)
