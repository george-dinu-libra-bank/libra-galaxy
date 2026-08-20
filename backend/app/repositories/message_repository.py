from __future__ import annotations

from dataclasses import dataclass, field

from supabase import Client

from app.core.errors import PersistenceError


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    sequence: int
    role: str
    text: str
    citations: list[dict] = field(default_factory=list)
    confidence: str | None = None
    channel: str = "text"
    created_at: str = ""


class MessageRepository:
    """Singurul strat care citeste/scrie ai_messages. Secventa e alocata aici, monoton crescatoare per conversatie."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def append(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        text: str,
        citations: list[dict] | None = None,
        confidence: str | None = None,
        channel: str = "text",
    ) -> Message:
        next_sequence = self._next_sequence(conversation_id)
        result = (
            self._client.table("ai_messages")
            .insert(
                {
                    "id_conversation": conversation_id,
                    "id_user": user_id,
                    "secventa": next_sequence,
                    "rol": role,
                    "continut": text,
                    "citari": citations or [],
                    "nivel_incredere": confidence,
                    "canal": channel,
                }
            )
            .execute()
        )
        if not result.data:
            raise PersistenceError("Nu am putut salva mesajul.")
        return self._to_message(result.data[0])

    def count(self, conversation_id: str) -> int:
        result = (
            self._client.table("ai_messages")
            .select("secventa")
            .eq("id_conversation", conversation_id)
            .order("secventa", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0]["secventa"] if result.data else 0

    def recent_window(self, conversation_id: str, window: int) -> list[Message]:
        result = (
            self._client.table("ai_messages")
            .select("*")
            .eq("id_conversation", conversation_id)
            .order("secventa", desc=True)
            .limit(window)
            .execute()
        )
        rows = list(reversed(result.data or []))
        return [self._to_message(row) for row in rows]

    def range(self, conversation_id: str, start_sequence: int, end_sequence: int) -> list[Message]:
        if start_sequence > end_sequence:
            return []
        result = (
            self._client.table("ai_messages")
            .select("*")
            .eq("id_conversation", conversation_id)
            .gte("secventa", start_sequence)
            .lte("secventa", end_sequence)
            .order("secventa")
            .execute()
        )
        return [self._to_message(row) for row in (result.data or [])]

    def list_for_conversation(self, conversation_id: str, limit: int = 200) -> list[Message]:
        result = (
            self._client.table("ai_messages")
            .select("*")
            .eq("id_conversation", conversation_id)
            .order("secventa")
            .limit(limit)
            .execute()
        )
        return [self._to_message(row) for row in (result.data or [])]

    def _next_sequence(self, conversation_id: str) -> int:
        return self.count(conversation_id) + 1

    @staticmethod
    def _to_message(row: dict) -> Message:
        return Message(
            id=row["id"],
            conversation_id=row["id_conversation"],
            sequence=row["secventa"],
            role=row["rol"],
            text=row["continut"],
            citations=row.get("citari") or [],
            confidence=row.get("nivel_incredere"),
            channel=row.get("canal", "text"),
            created_at=row.get("creat_la", ""),
        )
