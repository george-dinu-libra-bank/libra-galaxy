"""Citirea mesajelor bancii catre un client.

Merge cu clientul privilegiat, ca restul repozitoriilor din backend, dar
filtreaza intotdeauna pe utilizatorul din tool: nimeni nu ajunge la mesajele
altcuiva prin asistent.
"""

from anyio import to_thread
from supabase import Client

CAMPURI = "titlu,mesaj,tip,citita_la,creat_la"


class NotificareRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def ale_utilizatorului(self, user_id: str, limita: int = 5) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("notificari")
                .select(CAMPURI)
                .eq("id_utilizator", str(user_id))
                .order("creat_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        try:
            return await to_thread.run_sync(interogare)
        except Exception:
            # Tabela poate lipsi pe o baza fara migrarea 0020; asistentul
            # raspunde mai departe, fara mesajele bancii.
            return []
