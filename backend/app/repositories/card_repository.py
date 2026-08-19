from uuid import UUID

from anyio import to_thread
from supabase import Client

# Numarul de card, CVV-ul si data de expirare nu ies niciodata catre agent.
CAMPURI = "id,sold_curent,is_blocked,expira_la,creat_la"


class CardRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def list_owned(self, user_id: UUID) -> list[dict]:
        def query() -> list[dict]:
            response = (
                self._client.table("carduri")
                .select(CAMPURI)
                .eq("id_user", str(user_id))
                .order("creat_la")
                .execute()
            )
            return response.data or []

        return await to_thread.run_sync(query)
