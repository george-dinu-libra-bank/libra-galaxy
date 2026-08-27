from datetime import datetime
from uuid import UUID

from anyio import to_thread
from supabase import Client

CAMPURI = "id,suma,valuta,descriere,creat_la,id_user_send,id_user_recieve"


class TranzactieRepository:
    """Citeste tranzactiile utilizatorului curent.

    Clientul primit e cel al utilizatorului, deci RLS filtreaza deja in baza de
    date; filtrul explicit ramane ca a doua bariera, nu ca singura.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    async def intre(
        self,
        user_id: UUID,
        start: datetime,
        sfarsit: datetime,
        limita: int = 1000,
    ) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("tranzactii")
                .select(CAMPURI)
                .or_(f"id_user_send.eq.{user_id},id_user_recieve.eq.{user_id}")
                .gte("creat_la", start.isoformat())
                .lte("creat_la", sfarsit.isoformat())
                .order("creat_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def obtine(self, tranzactie_id: UUID) -> dict | None:
        """O tranzactie, dupa id — sau None daca nu exista sau nu e a
        utilizatorului curent al carui client a fost dat la construire. RLS
        (0002: "tranzactii proprii: select") face verificarea de proprietate
        aici, nu un filtru explicit pe user_id: daca randul vine inapoi, e al
        lui — folosit de api/routes/analiza.py inainte de a seta o categorie
        manuala, ca sa nu se poata suprascrie categoria unei tranzactii straine."""

        def interogare() -> dict | None:
            raspuns = (
                self._client.table("tranzactii")
                .select(CAMPURI)
                .eq("id", str(tranzactie_id))
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)
