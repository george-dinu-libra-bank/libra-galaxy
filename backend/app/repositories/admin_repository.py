from datetime import datetime
from decimal import Decimal
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

    # -- cereri de inchidere a contului -------------------------------------

    async def cereri_stergere(self, doar_deschise: bool = False) -> list[dict]:
        """Coada analistului, cu numele clientului si ce mai are la banca.

        Soldurile si creditele se aduc odata cu cererea, nu la deschiderea
        fiecarui rand: analistul are nevoie de ele ca sa stie daca poate apasa
        „Sterge", iar o citire per rand ar face lista de N ori mai lenta fara sa
        arate nimic in plus.
        """

        def interogare() -> list[dict]:
            constructor = (
                self._client.table("cereri_stergere_cont")
                .select("id,id_utilizator,motiv,status,creat_la,decis_la,motiv_refuz")
                .order("creat_la", desc=False)
            )
            if doar_deschise:
                constructor = constructor.eq("status", "in_asteptare")
            return constructor.execute().data or []

        cereri = await to_thread.run_sync(interogare)
        if not cereri:
            return []

        id_uri = list({c["id_utilizator"] for c in cereri})

        def context() -> tuple[dict, dict, dict]:
            profile = (
                self._client.table("profiles")
                .select("id,nume,email")
                .in_("id", id_uri)
                .execute()
                .data
                or []
            )
            conturi = (
                self._client.table("conturi_bancare")
                .select("id_user,nume,sold,valuta,blocat_administrativ")
                .in_("id_user", id_uri)
                .execute()
                .data
                or []
            )
            credite = (
                self._client.table("credite")
                .select("id_user,status")
                .in_("id_user", id_uri)
                .in_("status", ["activ", "restant"])
                .execute()
                .data
                or []
            )
            return (
                {p["id"]: p for p in profile},
                conturi,
                credite,
            )

        pe_id, conturi, credite = await to_thread.run_sync(context)

        for cerere in cereri:
            id_user = cerere["id_utilizator"]
            profil = pe_id.get(id_user) or {}
            ale_lui = [c for c in conturi if c["id_user"] == id_user]

            cerere["nume"] = profil.get("nume")
            cerere["email"] = profil.get("email")
            cerere["conturi"] = [
                {
                    "nume": c.get("nume"),
                    "sold": str(c.get("sold") or 0),
                    "valuta": c.get("valuta"),
                    "blocat": bool(c.get("blocat_administrativ")),
                }
                for c in ale_lui
            ]
            cerere["credite_in_derulare"] = sum(1 for c in credite if c["id_user"] == id_user)

        return cereri

    async def decide_stergere(
        self, id_cerere: UUID, id_admin: UUID, aproba: bool, motiv: str | None
    ) -> dict:
        def interogare() -> dict:
            return self._client.rpc(
                "decide_stergere_cont",
                {
                    "p_id_cerere": str(id_cerere),
                    "p_id_admin": str(id_admin),
                    "p_aproba": aproba,
                    "p_motiv": motiv,
                },
            ).execute().data

        return await to_thread.run_sync(interogare)

    async def sterge_client(self, id_cerere: UUID, id_admin: UUID) -> dict:
        """Poarta pe solduri sta in RPC, nu aici — vezi 0038_sterge_client.sql."""

        def interogare() -> dict:
            return self._client.rpc(
                "sterge_client",
                {"p_id_cerere": str(id_cerere), "p_id_admin": str(id_admin)},
            ).execute().data

        return await to_thread.run_sync(interogare)

    # -- cereri de inchidere a unui CONT BANCAR -----------------------------
    #
    # Alta operatiune decat cele de mai sus, si se confunda usor: acolo pleaca
    # omul din banca, aici se inchide un singur cont bancar si omul ramane.

    async def cereri_inchidere_cont(self, doar_deschise: bool = False) -> list[dict]:
        """Coada analistului pentru inchiderea conturilor.

        Acelasi principiu ca la `cereri_stergere`: tot ce-i trebuie ca sa decida
        vine intr-o singura citire. Aici asta inseamna si TOATE conturile
        deschise ale clientului, nu doar cel care se inchide — analistul trebuie
        sa poata alege destinatia banilor dintr-o lista, nu sa o ghiceasca.
        """

        def interogare() -> list[dict]:
            constructor = (
                self._client.table("cereri_inchidere_cont")
                .select(
                    "id,id_utilizator,id_cont,id_cont_destinatie,motiv,status,"
                    "creat_la,decis_la,motiv_refuz"
                )
                .order("creat_la", desc=False)
            )
            if doar_deschise:
                constructor = constructor.eq("status", "in_asteptare")
            return constructor.execute().data or []

        cereri = await to_thread.run_sync(interogare)
        if not cereri:
            return []

        id_uri = list({c["id_utilizator"] for c in cereri})

        def context() -> tuple[dict, list, list]:
            profile = (
                self._client.table("profiles")
                .select("id,nume,email,iban_cont")
                .in_("id", id_uri)
                .execute()
                .data
                or []
            )
            conturi = (
                self._client.table("conturi_bancare")
                .select("id,id_user,nume,iban,sold,valuta,blocat_administrativ,inchis_la")
                .in_("id_user", id_uri)
                .execute()
                .data
                or []
            )
            carduri = (
                self._client.table("carduri")
                .select("id,id_cont,numar_card,tip")
                .in_("id_user", id_uri)
                .is_("inchis_la", "null")
                .execute()
                .data
                or []
            )
            return {p["id"]: p for p in profile}, conturi, carduri

        pe_id, conturi, carduri = await to_thread.run_sync(context)

        for cerere in cereri:
            id_user = cerere["id_utilizator"]
            profil = pe_id.get(id_user) or {}
            iban_principal = profil.get("iban_cont")
            ale_lui = [c for c in conturi if c["id_user"] == id_user]
            contul = next((c for c in ale_lui if c["id"] == cerere["id_cont"]), None)

            cerere["nume"] = profil.get("nume")
            cerere["email"] = profil.get("email")
            cerere["cont"] = self._cont_admin(contul, iban_principal) if contul else None
            # Doar conturile DESCHISE si diferite de cel care se inchide pot primi
            # banii. Filtrul sta aici, nu in interfata: o lista din care lipsesc
            # optiunile imposibile e mai buna decat una in care sunt dezactivate.
            cerere["destinatii"] = [
                self._cont_admin(c, iban_principal)
                for c in ale_lui
                if c["id"] != cerere["id_cont"] and c.get("inchis_la") is None
            ]
            cerere["carduri"] = [
                {
                    "id": card["id"],
                    "ultimele4": str(card.get("numar_card") or "")[-4:],
                    "tip": card.get("tip"),
                }
                for card in carduri
                if card["id_cont"] == cerere["id_cont"]
            ]

        return cereri

    @staticmethod
    def _cont_admin(cont: dict, iban_principal: str | None) -> dict:
        """Forma in care un cont ajunge la analist. Un singur loc, ca randul care
        se inchide si cele care pot primi banii sa arate la fel."""
        return {
            "id": cont["id"],
            "nume": cont.get("nume"),
            "sold": str(cont.get("sold") or 0),
            "valuta": cont.get("valuta"),
            "blocat": bool(cont.get("blocat_administrativ")),
            "inchis": cont.get("inchis_la") is not None,
            "este_principal": bool(iban_principal) and cont.get("iban") == iban_principal,
        }

    async def decide_inchidere_cont(
        self,
        id_cerere: UUID,
        id_admin: UUID,
        aproba: bool,
        *,
        id_destinatie: UUID | None = None,
        motiv: str | None = None,
    ) -> dict:
        """Aproba (si muta banii) sau respinge.

        Toate garzile — contul principal, contul blocat, soldul negativ,
        destinatia invalida — stau in RPC (0040), nu aici. Un buton dezactivat e
        o sugestie; o exceptie din RPC e o regula.
        """

        def interogare() -> dict:
            if aproba:
                return self._client.rpc(
                    "inchide_cont_bancar",
                    {
                        "p_id_cerere": str(id_cerere),
                        "p_id_admin": str(id_admin),
                        "p_id_destinatie": str(id_destinatie) if id_destinatie else None,
                    },
                ).execute().data
            return self._client.rpc(
                "respinge_inchidere_cont",
                {
                    "p_id_cerere": str(id_cerere),
                    "p_id_admin": str(id_admin),
                    "p_motiv": motiv,
                },
            ).execute().data

        return await to_thread.run_sync(interogare)

    async def redeschide_cont(self, id_cont: UUID, id_admin: UUID) -> dict:
        """„Inchis, nu sters" nu inseamna nimic daca nimeni nu poate da inapoi."""

        def interogare() -> dict:
            return self._client.rpc(
                "redeschide_cont",
                {"p_id_cont": str(id_cont), "p_id_admin": str(id_admin)},
            ).execute().data

        return await to_thread.run_sync(interogare)

    async def sterge_utilizator_auth(self, id_user: str) -> None:
        """Randul din `auth.users`, dupa ce profilul a disparut prin RPC.

        Se face separat fiindca SQL-ul nostru n-are ce cauta in schema `auth`.
        Daca pica, profilul e deja sters si datele bancare la fel — ramane doar
        un cont de autentificare orfan, care nu mai poate ajunge nicaieri.
        """

        def interogare() -> None:
            self._client.auth.admin.delete_user(id_user)

        await to_thread.run_sync(interogare)

    # -- popriri -----------------------------------------------------------
    #
    # Nu e acelasi lucru cu blocarea contului, desi amandoua tin bani pe loc:
    # blocarea (0030) opreste TOT ce pleaca, poprirea (0047) indisponibilizeaza
    # o SUMA pe toate conturile omului. Pot fi si amandoua deodata.
    #
    # Toate garzile stau in RPC-uri, ca la inchiderea contului: cine cat mai are
    # de platit, ce se intampla cand clientul are mai putin decat suma poprita,
    # si ce se scrie in istoric. Aici e doar transportul.

    async def popriri(self, doar_active: bool = False) -> list[dict]:
        """Popririle, cu numele clientului si cu cat are efectiv in conturi.

        Disponibilul vine odata cu lista, dintr-o singura citire: „mai are de
        platit 5000" nu-i spune analistului daca poprirea se poate incasa azi,
        iar fara el ar cere randul al doilea pentru fiecare linie din coada.
        """

        def interogare() -> list[dict]:
            constructor = (
                self._client.table("popriri")
                .select(
                    "id,id_utilizator,creditor,dosar,suma_totala,suma_incasata,"
                    "valuta,status,creat_la,incheiat_la,observatie"
                )
                .order("creat_la", desc=True)
            )
            if doar_active:
                constructor = constructor.eq("status", "activa")
            return constructor.execute().data or []

        popriri = await to_thread.run_sync(interogare)
        if not popriri:
            return []

        id_uri = list({p["id_utilizator"] for p in popriri})

        def context() -> tuple[dict, dict]:
            profile = (
                self._client.table("profiles")
                .select("id,nume,email")
                .in_("id", id_uri)
                .execute()
                .data
                or []
            )
            conturi = (
                self._client.table("conturi_bancare")
                .select("id_user,sold,valuta")
                .in_("id_user", id_uri)
                .is_("inchis_la", "null")
                .execute()
                .data
                or []
            )
            return (
                {p["id"]: p for p in profile},
                conturi,
            )

        profile, conturi = await to_thread.run_sync(context)

        # Insumarea se face aici, nu in baza: `poprire_disponibil_total` e
        # revocata pentru oricine in afara de service_role si converteste prin
        # `converteste`, deci ar cere un apel per client. Pentru o coada de
        # analist, suma pe valuta contului e destul — conversia exacta o face
        # RPC-ul cand chiar se incaseaza.
        disponibil: dict[str, float] = {}
        for cont in conturi:
            id_user = cont["id_user"]
            disponibil[id_user] = disponibil.get(id_user, 0.0) + float(cont.get("sold") or 0)

        for poprire in popriri:
            profil = profile.get(poprire["id_utilizator"], {})
            poprire["nume"] = profil.get("nume")
            poprire["email"] = profil.get("email")
            poprire["disponibil"] = f"{disponibil.get(poprire['id_utilizator'], 0.0):.2f}"

        return popriri

    async def instituie_poprire(
        self,
        id_utilizator: UUID,
        creditor: str,
        suma: Decimal,
        id_admin: UUID,
        *,
        dosar: str | None = None,
        observatie: str | None = None,
    ) -> dict:
        def interogare() -> dict:
            return self._client.rpc(
                "instituie_poprire",
                {
                    "p_id_utilizator": str(id_utilizator),
                    "p_creditor": creditor,
                    "p_suma": str(suma),
                    "p_id_admin": str(id_admin),
                    "p_dosar": dosar,
                    "p_observatie": observatie,
                },
            ).execute().data

        return await to_thread.run_sync(interogare)

    async def incaseaza_poprire(
        self, id_poprire: UUID, id_admin: UUID, suma: Decimal | None = None
    ) -> dict:
        """Vireaza catre creditor. Fara suma, ia cat se poate acum."""

        def interogare() -> dict:
            return self._client.rpc(
                "incaseaza_poprirea",
                {
                    "p_id_poprire": str(id_poprire),
                    "p_id_admin": str(id_admin),
                    "p_suma": str(suma) if suma is not None else None,
                },
            ).execute().data

        return await to_thread.run_sync(interogare)

    async def storneaza_incasarea(
        self,
        id_poprire: UUID,
        id_admin: UUID,
        suma: Decimal | None = None,
        motiv: str | None = None,
    ) -> dict:
        """Reverse-ul incasarii: banii virati se intorc in contul clientului.

        Nu ridica poprirea — daca ea ramane activa, banii intorsi redevin
        indisponibili pe loc. Asta e corect: datoria a redevenit neplatita.
        """

        def interogare() -> dict:
            return self._client.rpc(
                "storneaza_incasarea",
                {
                    "p_id_poprire": str(id_poprire),
                    "p_id_admin": str(id_admin),
                    "p_suma": str(suma) if suma is not None else None,
                    "p_motiv": motiv,
                },
            ).execute().data

        return await to_thread.run_sync(interogare)

    async def ridica_poprire(
        self, id_poprire: UUID, id_admin: UUID, motiv: str | None = None
    ) -> dict:
        def interogare() -> dict:
            return self._client.rpc(
                "ridica_poprirea",
                {
                    "p_id_poprire": str(id_poprire),
                    "p_id_admin": str(id_admin),
                    "p_motiv": motiv,
                },
            ).execute().data

        return await to_thread.run_sync(interogare)




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

