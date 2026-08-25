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


# -----------------------------------------------------------------------------
# Analizele administratorului si urmarile lor
#
# Merge cu clientul privilegiat: politicile de pe analize_cont nu dau drept de
# insert nimanui, tocmai ca o analiza sa nu poata veni decat de aici, dupa ce
# rolul a fost verificat in aplicatie.
# -----------------------------------------------------------------------------


class AnalizaRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def scrie_analiza(self, campuri: dict) -> dict | None:
        def interogare() -> list[dict]:
            raspuns = self._client.table("analize_cont").insert(campuri).execute()
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None

    async def istoric(self, user_id: UUID, limita: int = 50) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("analize_cont")
                .select(
                    "id,id_utilizator,id_administrator,decizie,observatie,gravitate,"
                    "numar_semnalari,zile_analizate,conturi_blocate,creat_la"
                )
                .eq("id_utilizator", str(user_id))
                .order("creat_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def ultima_analiza(self, ids: list[UUID]) -> dict[str, dict]:
        """Ultima decizie pentru fiecare cont, ca lista sa arate ce s-a facut deja."""
        if not ids:
            return {}

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("analize_cont")
                .select("id_utilizator,decizie,observatie,creat_la")
                .in_("id_utilizator", [str(i) for i in ids])
                .order("creat_la", desc=True)
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        ultima: dict[str, dict] = {}
        for rand in randuri:  # deja ordonate descrescator
            ultima.setdefault(str(rand["id_utilizator"]), rand)
        return ultima

    # -- conturile ----------------------------------------------------------
    #
    # Blocarea administrativa sta pe cont, nu pe carduri. `carduri.is_blocked`
    # e butonul clientului, pentru un card pierdut; daca administratorul ar
    # folosi tot acel steag, cele doua s-ar calca reciproc — iar un client
    # care isi debloca propriul card si-ar ridica singur masura bancii.

    async def conturi(self, user_id: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("conturi_bancare")
                .select("id,nume,valuta,blocat_administrativ")
                .eq("id_user", str(user_id))
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def schimba_blocarea(self, user_id: UUID, blocat: bool) -> int:
        """Blocheaza sau deblocheaza toate conturile unui om. Intoarce cate a atins.

        Blocarea opreste tot ce pleaca din cont: platile cu cardurile lui si
        transferurile deopotriva. Bariera reala e un trigger in baza (0030), nu
        aceasta scriere — deci tine si daca cineva ocoleste aplicatia.
        """
        de_schimbat = [
            c["id"]
            for c in await self.conturi(user_id)
            if bool(c["blocat_administrativ"]) != blocat
        ]
        if not de_schimbat:
            return 0

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("conturi_bancare")
                .update({"blocat_administrativ": blocat})
                .in_("id", de_schimbat)
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return len(randuri) if randuri else len(de_schimbat)

    async def stare_conturi_toti(self, limita: int = 2000) -> dict[str, dict]:
        """Cate conturi are fiecare om si cate ii sunt blocate.

        O singura interogare pentru toata lista: varianta cu un apel per cont ar
        fi insemnat cateva sute de drumuri la baza pentru un singur ecran.
        """

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("conturi_bancare")
                .select("id_user,blocat_administrativ")
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)

        pe_om: dict[str, dict] = {}
        for rand in randuri:
            cheie = str(rand["id_user"])
            stare = pe_om.setdefault(cheie, {"total": 0, "blocate": 0})
            stare["total"] += 1
            if rand["blocat_administrativ"]:
                stare["blocate"] += 1
        return pe_om

    # -- notificarile -------------------------------------------------------

    async def scrie_notificare(
        self, user_id: UUID, titlu: str, mesaj: str, tip: str
    ) -> dict | None:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("notificari")
                .insert(
                    {
                        "id_utilizator": str(user_id),
                        "titlu": titlu,
                        "mesaj": mesaj,
                        "tip": tip,
                    }
                )
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        return randuri[0] if randuri else None
