from __future__ import annotations

from dataclasses import dataclass

from anyio import to_thread
from supabase import Client


@dataclass(frozen=True)
class ConversationSummary:
    conversation_id: str
    text: str
    covers_up_to_sequence: int


class SummaryRepository:
    """Singurul strat care citeste/scrie ai_conversation_summaries.

    Fiecare metoda ruleaza apelul sincron supabase-py pe un thread separat
    (to_thread.run_sync), ca sa nu blocheze bucla de evenimente asyncio."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def get(self, conversation_id: str) -> ConversationSummary:
        def interogare():
            return (
                self._client.table("ai_conversation_summaries")
                .select("*")
                .eq("id_conversation", conversation_id)
                .maybe_single()
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        # .maybe_single() intoarce None direct cand nu exista niciun rand.
        if not result or not result.data:
            return ConversationSummary(conversation_id=conversation_id, text="", covers_up_to_sequence=0)
        row = result.data
        return ConversationSummary(
            conversation_id=row["id_conversation"],
            text=row["rezumat"],
            covers_up_to_sequence=row["acopera_pana_la_secventa"],
        )

    async def upsert(self, conversation_id: str, user_id: str, text: str, covers_up_to_sequence: int) -> None:
        def interogare():
            return self._client.table("ai_conversation_summaries").upsert(
                {
                    "id_conversation": conversation_id,
                    "id_user": user_id,
                    "rezumat": text,
                    "acopera_pana_la_secventa": covers_up_to_sequence,
                },
                on_conflict="id_conversation",
            ).execute()

        await to_thread.run_sync(interogare)
