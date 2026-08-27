"""Sesizarile clientului catre banca."""

from anyio import to_thread
from supabase import Client

CAMPURI = "id,id_utilizator,subiect,rezumat,context,status,raspuns,raspuns_la,creat_la"


class SuportRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def deschisa_recenta(self, user_id: str) -> dict | None:
        """O sesizare a aceluiasi om, inca nerezolvata.

        Se verifica inainte de a scrie alta: un client care intreaba de trei ori
        acelasi lucru nu trebuie sa umple coada administratorului cu trei
        sesizari despre acelasi caz.
        """

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("cereri_suport")
                .select(CAMPURI)
                .eq("id_utilizator", str(user_id))
                .neq("status", "rezolvata")
                .order("creat_la", desc=True)
                .limit(1)
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None

    async def creeaza(self, campuri: dict) -> dict | None:
        def interogare() -> list[dict]:
            raspuns = self._client.table("cereri_suport").insert(campuri).execute()
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None

    async def ale_utilizatorului(self, user_id: str, limita: int = 20) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("cereri_suport")
                .select(CAMPURI)
                .eq("id_utilizator", str(user_id))
                .order("creat_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    # -- pentru administrator ------------------------------------------------

    async def coada(self, doar_deschise: bool = True, limita: int = 200) -> list[dict]:
        """Sesizarile de rezolvat, cele mai vechi primele.

        Ordinea e inversa fata de restul listelor din panou: aici nu conteaza ce
        e nou, ci cine asteapta de cel mai mult timp.
        """

        def interogare() -> list[dict]:
            q = self._client.table("cereri_suport").select(CAMPURI)
            if doar_deschise:
                q = q.neq("status", "rezolvata")
            raspuns = q.order("creat_la", desc=False).limit(limita).execute()
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def raspunde(
        self, id_cerere: str, raspuns: str, id_administrator: str, status: str
    ) -> dict | None:
        def interogare() -> list[dict]:
            rezultat = (
                self._client.table("cereri_suport")
                .update(
                    {
                        "raspuns": raspuns,
                        "id_administrator": str(id_administrator),
                        "raspuns_la": "now()",
                        "status": status,
                    }
                )
                .eq("id", str(id_cerere))
                .execute()
            )
            return rezultat.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None
