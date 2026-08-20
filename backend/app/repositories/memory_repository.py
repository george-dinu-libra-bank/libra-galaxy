from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from supabase import Client


@dataclass(frozen=True)
class UserMemory:
    memory_type: str
    content: str


class MemoryRepository:
    """Memorie per utilizator (docs/AI_ARCHITECTURE.md #6) — niciodata stare bancara.

    Extragerea automata de memorii (dintr-un LLM) e scop viitor; azi expunem doar
    citirea, ca sectiunea de context sa existe fara sa inventeze un scriitor
    fara caz de utilizare concret.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    def list_active(self, user_id: str, limit: int = 20) -> list[UserMemory]:
        now_iso = datetime.now(timezone.utc).isoformat()
        result = (
            self._client.table("ai_user_memories")
            .select("tip, continut, expira_la")
            .eq("id_user", user_id)
            .or_(f"expira_la.is.null,expira_la.gt.{now_iso}")
            .order("creat_la", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        return [UserMemory(memory_type=row["tip"], content=row["continut"]) for row in rows]
