"""Cazurile de investigatie si firul lor de discutie (migrarea 0051).

Toate scrierile trec pe aici, cu client de service-role. Tabelele au politici
RLS doar de SELECT, deci un client nu poate adauga singur un mesaj „de la banca"
in propriul dosar nici daca ar ajunge la API cu tokenul lui.
"""

from uuid import UUID

from anyio import to_thread
from supabase import Client

CAMPURI_CAZ = (
    "id,id_utilizator,id_administrator,stare,motiv_deschidere,"
    "gravitate,numar_semnalari,rezultat,deschis_la,inchis_la"
)
CAMPURI_MESAJ = (
    "id,id_caz,autor,id_autor,text,structura,propus_de_agent,editat_de_om,creat_la"
)

# Starile din care cazul mai poate primi mesaje. Aceleasi cu cele excluse de
# indexul partial `caz_deschise_idx` din migrare — daca se schimba una, se
# schimba amandoua.
STARI_INCHISE = ("rezolvat", "escalat", "inchis")


class CazRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    # -- cazul ---------------------------------------------------------------

    async def creeaza(self, campuri: dict) -> dict | None:
        def interogare() -> list[dict]:
            raspuns = self._client.table("caz_investigatie").insert(campuri).execute()
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None

    async def caz(self, id_caz: UUID | str) -> dict | None:
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("caz_investigatie")
                .select(CAMPURI_CAZ)
                .eq("id", str(id_caz))
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    async def deschis_pentru(self, user_id: UUID | str) -> dict | None:
        """Cazul nerezolvat al aceluiasi om, daca exista.

        Doua cazuri deschise pe acelasi client inseamna doua fire de discutie
        despre aceleasi plati si un client care primeste doua intrebari
        diferite de la aceeasi banca.
        """

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("caz_investigatie")
                .select(CAMPURI_CAZ)
                .eq("id_utilizator", str(user_id))
                .not_.in_("stare", list(STARI_INCHISE))
                .order("deschis_la", desc=True)
                .limit(1)
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None

    async def ale_utilizatorului(self, user_id: UUID | str, limita: int = 20) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("caz_investigatie")
                .select(CAMPURI_CAZ)
                .eq("id_utilizator", str(user_id))
                .order("deschis_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def coada(self, doar_deschise: bool = True, limita: int = 200) -> list[dict]:
        """Coada administratorului: cel mai vechi caz nerezolvat primul.

        Ca la sesizari — aici nu conteaza ce e nou, ci cine asteapta de cel mai
        mult timp cu contul blocat.
        """

        def interogare() -> list[dict]:
            q = self._client.table("caz_investigatie").select(CAMPURI_CAZ)
            if doar_deschise:
                q = q.not_.in_("stare", list(STARI_INCHISE))
            raspuns = q.order("deschis_la", desc=False).limit(limita).execute()
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def schimba_starea(
        self,
        id_caz: UUID | str,
        stare: str,
        rezultat: str | None = None,
        inchide: bool = False,
    ) -> dict | None:
        campuri: dict = {"stare": stare}
        if rezultat is not None:
            campuri["rezultat"] = rezultat
        if inchide:
            campuri["inchis_la"] = "now()"

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("caz_investigatie")
                .update(campuri)
                .eq("id", str(id_caz))
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None

    # -- tranzactiile cazului ------------------------------------------------

    async def leaga_tranzactii(self, id_caz: UUID | str, tranzactii: list[dict]) -> int:
        """`tranzactii`: randuri cu `id_tranzactie` si, optional, `motiv`."""
        if not tranzactii:
            return 0

        randuri = [
            {
                "id_caz": str(id_caz),
                "id_tranzactie": str(t["id_tranzactie"]),
                "motiv": t.get("motiv"),
            }
            for t in tranzactii
        ]

        def interogare() -> list[dict]:
            raspuns = self._client.table("caz_tranzactie").insert(randuri).execute()
            return raspuns.data or []

        rezultat = await to_thread.run_sync(interogare)
        return len(rezultat)

    async def tranzactiile(self, id_caz: UUID | str) -> list[dict]:
        """Legaturile cazului, cu datele platii aduse din `tranzactii`.

        Un singur apel cu join, nu N+1: un caz poate avea zeci de plati
        semnalate, iar ecranul administratorului le arata pe toate deodata.
        """

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("caz_tranzactie")
                .select("motiv,id_tranzactie,tranzactii(id,suma,valuta,descriere,creat_la)")
                .eq("id_caz", str(id_caz))
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    # -- firul de discutie ---------------------------------------------------

    async def adauga_mesaj(self, campuri: dict) -> dict | None:
        def interogare() -> list[dict]:
            raspuns = self._client.table("caz_mesaj").insert(campuri).execute()
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None

    async def mesajele(self, id_caz: UUID | str, limita: int = 200) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("caz_mesaj")
                .select(CAMPURI_MESAJ)
                .eq("id_caz", str(id_caz))
                .order("creat_la", desc=False)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)
