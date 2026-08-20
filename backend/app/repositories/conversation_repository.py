from __future__ import annotations

from dataclasses import dataclass

from anyio import to_thread
from supabase import Client

from app.core.errors import PersistenceError, ResourceNotFoundError


@dataclass(frozen=True)
class Conversation:
    id: str
    user_id: str
    title: str
    summary_watermark: int
    created_at: str
    updated_at: str


class ConversationRepository:
    """Singurul strat care citeste/scrie ai_conversations. Fiecare interogare filtreaza pe id_user.

    Fiecare metoda ruleaza apelul sincron supabase-py pe un thread separat
    (to_thread.run_sync) — altfel un singur round-trip HTTP ar bloca toata
    bucla de evenimente asyncio, serializand cererile concurente ale tuturor
    utilizatorilor pe un singur thread."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def create(self, user_id: str, title: str = "Conversație nouă") -> Conversation:
        def interogare():
            return self._client.table("ai_conversations").insert({"id_user": user_id, "titlu": title}).execute()

        result = await to_thread.run_sync(interogare)
        if not result.data:
            raise PersistenceError("Nu am putut crea conversatia.")
        return self._to_conversation(result.data[0])

    async def get_owned(self, user_id: str, conversation_id: str) -> Conversation:
        def interogare():
            return (
                self._client.table("ai_conversations")
                .select("*")
                .eq("id", conversation_id)
                .eq("id_user", user_id)
                .maybe_single()
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        # .maybe_single() intoarce None direct cand nu exista niciun rand.
        if not result or not result.data:
            raise ResourceNotFoundError("Conversatia nu a fost gasita.")
        return self._to_conversation(result.data)

    async def list_for_user(self, user_id: str, limit: int = 50) -> list[Conversation]:
        def interogare():
            return (
                self._client.table("ai_conversations")
                .select("*")
                .eq("id_user", user_id)
                .order("actualizat_la", desc=True)
                .limit(limit)
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        return [self._to_conversation(row) for row in (result.data or [])]

    async def delete_owned(self, user_id: str, conversation_id: str) -> None:
        # Filtrat pe owner, nu doar pe id — un id ghicit nu poate sterge la altul.
        # Mesajele/rezumatul/atasamentele dispar prin "on delete cascade"
        # (0004/0005_ai_asistent*.sql). Idempotent: sterge 0 randuri fara eroare
        # daca id-ul nu exista sau nu e al utilizatorului.
        def interogare():
            return self._client.table("ai_conversations").delete().eq("id", conversation_id).eq(
                "id_user", user_id
            ).execute()

        await to_thread.run_sync(interogare)

    async def touch(self, conversation_id: str) -> None:
        def interogare():
            return self._client.table("ai_conversations").update({"actualizat_la": "now()"}).eq(
                "id", conversation_id
            ).execute()

        await to_thread.run_sync(interogare)

    async def set_title_if_default(self, conversation_id: str, title: str) -> None:
        def interogare():
            return self._client.table("ai_conversations").update({"titlu": title}).eq(
                "id", conversation_id
            ).eq("titlu", "Conversație nouă").execute()

        await to_thread.run_sync(interogare)

    async def update_watermark(self, conversation_id: str, watermark: int) -> None:
        def interogare():
            return self._client.table("ai_conversations").update({"summary_watermark": watermark}).eq(
                "id", conversation_id
            ).execute()

        await to_thread.run_sync(interogare)

    @staticmethod
    def _to_conversation(row: dict) -> Conversation:
        return Conversation(
            id=row["id"],
            user_id=row["id_user"],
            title=row["titlu"],
            summary_watermark=row["summary_watermark"],
            created_at=row["creat_la"],
            updated_at=row["actualizat_la"],
        )
