from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from anyio import to_thread
from supabase import Client

from app.core.errors import PersistenceError


@dataclass(frozen=True)
class UserMemory:
    memory_type: str
    content: str


class MemoryRepository:
    """Memorie per utilizator (docs/AI_ARCHITECTURE.md #6) — niciodata stare bancara.

    Fiecare metoda ruleaza apelul sincron supabase-py pe un thread separat
    (to_thread.run_sync), ca sa nu blocheze bucla de evenimente asyncio.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    async def list_active(self, user_id: str, limit: int = 20) -> list[UserMemory]:
        now_iso = datetime.now(timezone.utc).isoformat()

        def interogare():
            return (
                self._client.table("ai_user_memories")
                .select("tip, continut, expira_la")
                .eq("id_user", user_id)
                .or_(f"expira_la.is.null,expira_la.gt.{now_iso}")
                .order("creat_la", desc=True)
                .limit(limit)
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        rows = result.data or []
        return [UserMemory(memory_type=row["tip"], content=row["continut"]) for row in rows]

    async def write(
        self, user_id: str, memory_type: str, content: str, expires_at: str | None = None
    ) -> None:
        """Scrie o memorie durabila (preferinta/intentie declarata/fapt conversational).

        Apelantul (memory/extraction.py, prin orchestrator) raspunde de a nu
        trimite niciodata stare bancara aici (solduri, sume, IBAN-uri) — acest
        strat doar persista ce i se da, nu mai filtreaza o data in plus.
        """

        def interogare():
            return (
                self._client.table("ai_user_memories")
                .insert(
                    {
                        "id_user": user_id,
                        "tip": memory_type,
                        "continut": content,
                        "expira_la": expires_at,
                    }
                )
                .execute()
            )

        result = await to_thread.run_sync(interogare)
        if not result.data:
            raise PersistenceError("Nu am putut salva memoria.")
