from uuid import UUID

from anyio import to_thread
from supabase import Client

# Numarul de card, CVV-ul si data expirarii nu ies niciodata catre un agent.
# Coloanele trebuie sa existe in baza reala, nu doar in migrarile din repo:
# schema din cloud a luat-o inainte (vezi conturi_bancare, absent din migrari).
CAMPURI = "id,sold_curent,is_blocked,creat_la"


class CardRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def ale_utilizatorului(self, user_id: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("carduri")
                .select(CAMPURI)
                .eq("id_user", str(user_id))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)
