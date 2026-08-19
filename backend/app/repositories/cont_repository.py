from uuid import UUID

from anyio import to_thread
from supabase import Client

# Soldul real al utilizatorului sta pe cont, nu pe card (vezi lib/actions/transfer.ts).
CAMPURI = "id,nume,iban,sold,creat_la"


class ContRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def ale_utilizatorului(self, user_id: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("conturi_bancare")
                .select(CAMPURI)
                .eq("id_user", str(user_id))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)
