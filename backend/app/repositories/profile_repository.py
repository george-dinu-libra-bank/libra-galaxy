from uuid import UUID

from anyio import to_thread
from supabase import Client


class ProfileRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def get_owned_profile(self, user_id: UUID) -> dict | None:
        def query() -> dict | None:
            response = (
                self._client.table("profiles")
                .select("id,nume,cnp,telefon,email,iban_cont,creat_la,modificat_la")
                .eq("id", str(user_id))
                .maybe_single()
                .execute()
            )
            return response.data

        return await to_thread.run_sync(query)
