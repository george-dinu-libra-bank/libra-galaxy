from datetime import datetime
from uuid import UUID

from anyio import to_thread
from supabase import Client

CAMPURI = "id,suma,valuta,descriere,creat_la,id_user_send,id_user_recieve"


class TransactionRepository:
    """Citeste tranzactiile utilizatorului curent. RLS filtreaza deja pe client,
    filtrul explicit pe id_user ramane ca a doua bariera."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def list_between(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[dict]:
        def query() -> list[dict]:
            response = (
                self._client.table("tranzactii")
                .select(CAMPURI)
                .or_(f"id_user_send.eq.{user_id},id_user_recieve.eq.{user_id}")
                .gte("creat_la", start.isoformat())
                .lte("creat_la", end.isoformat())
                .order("creat_la", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []

        return await to_thread.run_sync(query)
