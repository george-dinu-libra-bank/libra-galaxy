from datetime import datetime
from uuid import UUID

from anyio import to_thread
from supabase import Client

CAMPURI_TRANZACTIE = "id,suma,valuta,descriere,creat_la,id_user_send,id_user_recieve"
CAMPURI_PROFIL = "id,nume,email,telefon,iban_cont,creat_la"


class AdminRepository:
    """Citirile care trec dincolo de un singur utilizator.

    Separat de celelalte repository-uri intentionat: dreptul de a citi datele
    altcuiva e altul decat dreptul de a le citi pe ale tale, si se vede mai bine
    daca si codul e altul.

    Clientul primit e tot al administratorului, cu tokenul lui — nu service_role.
    Politicile din 0004 il lasa sa treaca fiindca e administrator in baza de
    date; daca i se ia rolul, urmatoarea cerere nu mai intoarce nimic, fara sa
    fie nevoie de vreo schimbare aici.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    async def profil(self, user_id: UUID) -> dict | None:
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("profiles")
                .select(CAMPURI_PROFIL)
                .eq("id", str(user_id))
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    async def profiluri(self, ids: list[UUID]) -> dict[str, dict]:
        """Profilurile cerute, pe id — ca sa nu facem cate o cerere de fiecare."""
        if not ids:
            return {}

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("profiles")
                .select(CAMPURI_PROFIL)
                .in_("id", [str(i) for i in ids])
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return {str(rand["id"]): rand for rand in randuri}

    async def utilizatori_cu_plati(self, start: datetime, limita: int = 500) -> list[UUID]:
        """Cine a trimis bani de la `start` incoace.

        Numai ei pot avea neregularitati: detectorul se uita la plati de iesire.
        """

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("tranzactii")
                .select("id_user_send")
                .gte("creat_la", start.isoformat())
                .order("creat_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)

        # Randurile fara expeditor sunt incasari; se sar aici, nu in interogare,
        # ca sa nu depindem de sintaxa de negare a clientului.
        vazuti: list[UUID] = []
        deja = set()
        for rand in randuri:
            brut = rand.get("id_user_send")
            if not brut:
                continue
            id_user = str(brut)
            if id_user not in deja:
                deja.add(id_user)
                vazuti.append(UUID(id_user))
        return vazuti

    async def tranzactii(
        self, user_id: UUID, start: datetime, sfarsit: datetime, limita: int = 1000
    ) -> list[dict]:
        """Aceleasi campuri ca TranzactieRepository.intre, pentru alt utilizator."""

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("tranzactii")
                .select(CAMPURI_TRANZACTIE)
                .or_(f"id_user_send.eq.{user_id},id_user_recieve.eq.{user_id}")
                .gte("creat_la", start.isoformat())
                .lte("creat_la", sfarsit.isoformat())
                .order("creat_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def scrie_acces(
        self,
        id_administrator: UUID,
        actiune: str,
        id_utilizator: UUID | None = None,
        detalii: str | None = None,
    ) -> None:
        """Urma citirii. Nu opreste cererea daca esueaza.

        Un raport care crapa fiindca n-a putut scrie o linie de audit ar fi mai
        rau decat unul livrat cu urma lipsa — dar lipsa se vede in loguri.
        """

        def interogare() -> None:
            self._client.table("acces_administrator").insert(
                {
                    "id_administrator": str(id_administrator),
                    "id_utilizator": str(id_utilizator) if id_utilizator else None,
                    "actiune": actiune,
                    "detalii": detalii,
                }
            ).execute()

        await to_thread.run_sync(interogare)
