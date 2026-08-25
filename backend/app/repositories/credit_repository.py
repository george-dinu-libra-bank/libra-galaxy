"""Accesul la datele de creditare.

Primeste clientul la construire, ca restul repository-urilor, si nu il fabrica
singur (app/infrastructure/supabase_client.py e singurul loc care face asta).
Clientul asteptat aici e cel cu service_role: tabelele credit_* nu au politici de
insert/update pentru 'authenticated', iar cele trei RPC-uri de operatiuni au
`execute` revocat pentru orice rol in afara de service_role.

Metodele sunt async si impacheteaza apelurile sincrone din supabase-py in
`to_thread.run_sync`, ca in ContRepository si TranzactieRepository — altfel un
apel de retea ar bloca bucla de evenimente a lui FastAPI.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from anyio import to_thread
from supabase import Client

logger = logging.getLogger(__name__)

CAMPURI_PRODUS = (
    "id,slug,nume,dobanda_anuala,suma_min,suma_max,luni_min,luni_max,"
    "varsta_min,varsta_max,venit_net_minim,vechime_angajator_luni,vechime_venituri_luni"
)
CAMPURI_CERERE = (
    "id,id_user,id_produs,suma_ceruta,luni,scop,venit_declarat,angajator,"
    "vechime_angajator_luni,obligatii_declarate,venit_folosit,obligatii_folosite,"
    "dti,scor,motive,explicatie,rata_lunara,dae,oferta_expira_la,status,creat_la"
)
CAMPURI_CREDIT = (
    "id,id_cerere,id_user,id_cont_creditare,principal,dobanda_anuala,luni,"
    "rata_lunara,dae,sold_ramas,data_acordarii,semnat_la,status,inchis_la,creat_la"
)
CAMPURI_RATA = (
    "id,numar_rata,scadenta,principal_rata,dobanda_rata,rata_totala,"
    "sold_dupa,status,platita_la,id_tranzactie"
)
CAMPURI_DOCUMENT = (
    "id,id_cerere,id_user,tip,storage_path,content_type,marime_octeti,extras,"
    "status,hash_fisier,venit_confirmat,confirmat_de,confirmat_la,sters_la,creat_la"
)

CAMPURI_MESAJ = "id,id_cerere,autor,id_autor,text,id_document,creat_la,citit_de_client_la"

BUCKET_DOCUMENTE = "credit-documente"
# Cat traieste un link catre o adeverinta. Cinci minute inseamna ca un URL
# copiat din bara de adrese nu mai deschide nimic pana ajunge altundeva.
SECUNDE_URL_SEMNAT = 300


class CreditRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    # -- catalog ------------------------------------------------------------

    async def produs(self, slug: str) -> dict | None:
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("credit_produse")
                .select(CAMPURI_PRODUS)
                .eq("slug", slug)
                .eq("activ", True)
                .maybe_single()
                .execute()
            )
            # .maybe_single() intoarce None direct cand nu exista rand, nu un
            # raspuns cu .data=None (REGULI.md #1).
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    # -- solicitant ---------------------------------------------------------

    async def profil(self, user_id: UUID) -> dict | None:
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("profiles")
                .select("id,nume,cnp,verification_status,creat_la")
                .eq("id", str(user_id))
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    async def conturi(self, user_id: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("conturi_bancare")
                .select("id,nume,iban,sold,valuta,creat_la")
                .eq("id_user", str(user_id))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def tranzactii_pentru_venit(self, user_id: UUID, luni: int = 14) -> list[dict]:
        """Randuri brute, in forma pe care o asteapta `ml.caracteristici.normalizeaza`.

        Se cer mai multe luni decat cere produsul (12): detectorul are nevoie de
        istoric ca sa poata confirma un ritm, nu doar sa il constate.
        """
        de_la = datetime.now(timezone.utc) - timedelta(days=31 * luni)

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("tranzactii")
                .select("id,suma,valuta,descriere,creat_la,id_user_send,id_user_recieve")
                .or_(f"id_user_send.eq.{user_id},id_user_recieve.eq.{user_id}")
                .gte("creat_la", de_la.isoformat())
                .order("creat_la", desc=True)
                .limit(2000)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def expuneri_birou(self, cnp: str) -> list[dict]:
        """Ce datoreaza omul la alte banci, dupa registrul intern simulat."""

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_bureau_simulat")
                .select("banca,tip_produs,rata_lunara,sold")
                .eq("cnp", cnp)
                .eq("activ", True)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def rate_lunare_credite_active(self, user_id: UUID) -> float:
        """Obligatiile pe care le are deja la Galaxy Bank.

        Fara asta, cine ia doua credite la rand ar fi evaluat de doua ori ca si
        cum n-ar avea niciunul.
        """

        def interogare() -> float:
            raspuns = (
                self._client.table("credite")
                .select("rata_lunara")
                .eq("id_user", str(user_id))
                .in_("status", ["activ", "restant"])
                .execute()
            )
            return sum(float(rand["rata_lunara"]) for rand in (raspuns.data or []))

        return await to_thread.run_sync(interogare)

    # -- cereri -------------------------------------------------------------

    async def creeaza_cerere(self, campuri: dict[str, Any]) -> dict:
        def interogare() -> dict:
            raspuns = self._client.table("credit_cereri").insert(campuri).execute()
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    async def cerere(self, id_cerere: UUID) -> dict | None:
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("credit_cereri")
                .select(CAMPURI_CERERE)
                .eq("id", str(id_cerere))
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    async def cereri_utilizator(self, user_id: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_cereri")
                .select(CAMPURI_CERERE)
                .eq("id_user", str(user_id))
                .order("creat_la", desc=True)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def cereri_in_analiza(self) -> list[dict]:
        """Coada de analiza manuala, cea mai veche prima.

        Nu filtreaza pe utilizator: e o vedere de administrator, iar accesul e
        oprit mai sus, in dependinta de ruta si in politicile RLS.
        """

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_cereri")
                .select(CAMPURI_CERERE + ",profiles(nume,cnp)")
                .eq("status", "analiza_manuala")
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def cereri_toate(self, status: str | None = None, limita: int = 200) -> list[dict]:
        """Vederea de administrator peste toate cererile, optional filtrata.

        Cea mai noua prima, invers fata de coada de analiza: acolo conteaza cine
        asteapta de cel mai mult timp, aici ce s-a intamplat recent.
        """

        def interogare() -> list[dict]:
            cerere = (
                self._client.table("credit_cereri")
                .select(CAMPURI_CERERE + ",profiles(nume)")
                .order("creat_la", desc=True)
                .limit(limita)
            )
            if status:
                cerere = cerere.eq("status", status)
            raspuns = cerere.execute()
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def credite_toate(self, limita: int = 200) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credite")
                .select(CAMPURI_CREDIT + ",profiles(nume)")
                .order("creat_la", desc=True)
                .limit(limita)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def actualizeaza_cerere(self, id_cerere: UUID, campuri: dict[str, Any]) -> dict:
        def interogare() -> dict:
            raspuns = (
                self._client.table("credit_cereri")
                .update(campuri)
                .eq("id", str(id_cerere))
                .execute()
            )
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    # -- verificari si documente -------------------------------------------

    async def salveaza_verificare(self, campuri: dict[str, Any]) -> dict:
        def interogare() -> dict:
            raspuns = self._client.table("credit_verificari_venit").insert(campuri).execute()
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    async def verificari(self, id_cerere: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_verificari_venit")
                .select("sursa,venit_constatat,obligatii_constatate,incredere,detalii,creat_la")
                .eq("id_cerere", str(id_cerere))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def salveaza_document(self, campuri: dict[str, Any]) -> dict:
        def interogare() -> dict:
            raspuns = self._client.table("credit_documente").insert(campuri).execute()
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    async def document(self, id_document: UUID) -> dict | None:
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("credit_documente")
                .select(CAMPURI_DOCUMENT)
                .eq("id", str(id_document))
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    async def documente(self, id_cerere: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_documente")
                .select(CAMPURI_DOCUMENT)
                .eq("id_cerere", str(id_cerere))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    # -- fir de discutie ----------------------------------------------------

    async def mesaje(self, id_cerere: UUID) -> list[dict]:
        """Firul intreg, in ordine cronologica.

        Fara limita: un dosar de credit are cateva mesaje, nu mii, iar taierea
        ar face ca tocmai inceputul discutiei — unde se cere ceva — sa dispara.
        """
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_mesaje")
                .select(CAMPURI_MESAJ)
                .eq("id_cerere", str(id_cerere))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def adauga_mesaj(self, campuri: dict[str, Any]) -> dict:
        def interogare() -> dict:
            raspuns = self._client.table("credit_mesaje").insert(campuri).execute()
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    async def marcheaza_mesaje_citite(self, id_cerere: UUID) -> None:
        """Mesajele care nu-s ale clientului devin citite.

        `is_("citit_de_client_la", "null")` face operatia idempotenta: a doua
        deschidere a firului nu rescrie momentul primei citiri.
        """
        def interogare() -> None:
            (
                self._client.table("credit_mesaje")
                .update({"citit_de_client_la": datetime.now(timezone.utc).isoformat()})
                .eq("id_cerere", str(id_cerere))
                .neq("autor", "client")
                .is_("citit_de_client_la", "null")
                .execute()
            )

        await to_thread.run_sync(interogare)

    async def numara_necitite(self, id_cereri: list[UUID]) -> dict[str, int]:
        """Cate mesaje necitite are fiecare cerere — pentru bulina.

        O singura interogare pentru toata lista, nu una per cerere: ecranul de
        credite si dashboardul o cer la fiecare afisare.
        """
        if not id_cereri:
            return {}

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_mesaje")
                .select("id_cerere")
                .in_("id_cerere", [str(i) for i in id_cereri])
                .neq("autor", "client")
                .is_("citit_de_client_la", "null")
                .execute()
            )
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        contor: dict[str, int] = {}
        for rand in randuri:
            cheie = str(rand["id_cerere"])
            contor[cheie] = contor.get(cheie, 0) + 1
        return contor

    async def notifica(self, id_utilizator: UUID, titlu: str, mesaj: str, tip: str) -> None:
        """Un rand in `public.notificari`, pe care clientul il vede in clopotel.

        Tabela e a altcuiva (nu are migratie in repo) si e proiectata pentru
        citire directa din client: politicile RLS lasa fiecare om sa-si vada si
        sa-si marcheze propriile randuri, dar nu exista politica de INSERT —
        scrierea ramane a service_role-ului, adica a noastra.

        Nu arunca niciodata: notificarea e un plus peste firul de discutie, care
        e oricum vizibil in aplicatie. Un esec aici n-are voie sa rupa trimiterea
        mesajului.
        """
        def interogare() -> None:
            self._client.table("notificari").insert({
                "id_utilizator": str(id_utilizator),
                "titlu": titlu[:200],
                "mesaj": mesaj[:4000],
                "tip": tip,
            }).execute()

        try:
            await to_thread.run_sync(interogare)
        except Exception:
            logger.exception("nu am putut scrie notificarea pentru %s", id_utilizator)

    async def documente_cu_hash(self, hash_fisier: str, exclude_id_cerere: UUID) -> list[dict]:
        """Documente cu acelasi continut (sha256), de la ALTA cerere — pentru
        semnalul 'document_reutilizat' din pipeline-ul AI. Foloseste
        `credit_documente_hash_idx` (0018), altfel ar fi un scan pe toata tabela
        la fiecare deschidere de dosar."""
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_documente")
                .select("id,id_cerere,id_user,creat_la")
                .eq("hash_fisier", hash_fisier)
                .neq("id_cerere", str(exclude_id_cerere))
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def actualizeaza_document(self, id_document: UUID, campuri: dict[str, Any]) -> dict:
        def interogare() -> dict:
            raspuns = (
                self._client.table("credit_documente")
                .update(campuri)
                .eq("id", str(id_document))
                .execute()
            )
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    async def documente_expirate(self, inainte_de: datetime) -> list[dict]:
        """Documentele al caror fisier trebuie sters: dosar inchis de destul timp.

        Filtrul `sters_la is null` e ce face curatarea idempotenta — un al doilea
        apel, concurent sau nu, nu mai vede randurile deja curatate. Acelasi
        tipar ca la incasarea ratelor, si din acelasi motiv: nu exista cron in
        proiect, deci operatiunea se declanseaza din citiri obisnuite si trebuie
        sa suporte sa fie pornita de doua ori deodata.
        """

        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_documente")
                .select(CAMPURI_DOCUMENT + ",credit_cereri!inner(finalizat_la)")
                .is_("sters_la", "null")
                .lte("credit_cereri.finalizat_la", inainte_de.isoformat())
                .limit(50)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    # -- storage (bucket privat 'credit-documente') -------------------------

    async def urca_document(self, cale: str, continut: bytes, content_type: str) -> None:
        def interogare() -> None:
            self._client.storage.from_(BUCKET_DOCUMENTE).upload(
                cale, continut, {"content-type": content_type}
            )

        await to_thread.run_sync(interogare)

    async def url_document(self, cale: str, secunde: int = SECUNDE_URL_SEMNAT) -> str | None:
        """Link temporar catre document. Niciodata public: bucket-ul e privat.

        Intoarce None in loc sa arunce — un link care nu s-a putut genera nu
        trebuie sa darame ecranul analistului, care are si restul dosarului de
        citit.
        """

        def interogare() -> str | None:
            try:
                raspuns = self._client.storage.from_(BUCKET_DOCUMENTE).create_signed_url(
                    cale, secunde
                )
            except Exception:
                return None
            if isinstance(raspuns, dict):
                return raspuns.get("signedURL") or raspuns.get("signedUrl")
            return None

        return await to_thread.run_sync(interogare)

    async def sterge_document(self, cale: str) -> None:
        def interogare() -> None:
            self._client.storage.from_(BUCKET_DOCUMENTE).remove([cale])

        await to_thread.run_sync(interogare)

    # -- credite ------------------------------------------------------------

    async def credit(self, id_credit: UUID) -> dict | None:
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("credite")
                .select(CAMPURI_CREDIT)
                .eq("id", str(id_credit))
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    async def credite_utilizator(self, user_id: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credite")
                .select(CAMPURI_CREDIT)
                .eq("id_user", str(user_id))
                .order("creat_la", desc=True)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def rate(self, id_credit: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_rate")
                .select(CAMPURI_RATA)
                .eq("id_credit", str(id_credit))
                .order("numar_rata")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def eveniment(self, campuri: dict[str, Any]) -> None:
        def interogare() -> None:
            self._client.table("credit_evenimente").insert(campuri).execute()

        await to_thread.run_sync(interogare)

    # -- operatiuni (RPC atomic, 0010_credite_operatiuni.sql) ---------------

    async def acorda(
        self,
        id_cerere: UUID,
        id_cont: UUID,
        rata_lunara: float,
        dae: float,
        grafic: list[dict],
        semnatura: dict,
    ) -> dict:
        def interogare() -> dict:
            raspuns = self._client.rpc(
                "credit_acorda",
                {
                    "p_id_cerere": str(id_cerere),
                    "p_id_cont": str(id_cont),
                    "p_rata_lunara": rata_lunara,
                    "p_dae": dae,
                    "p_grafic": grafic,
                    "p_semnatura": semnatura,
                },
            ).execute()
            return raspuns.data

        return await to_thread.run_sync(interogare)

    async def incaseaza_rate(self, id_credit: UUID, pana_la: date | None = None) -> dict:
        def interogare() -> dict:
            raspuns = self._client.rpc(
                "credit_incaseaza_rate",
                {
                    "p_id_credit": str(id_credit),
                    "p_pana_la": pana_la.isoformat() if pana_la else None,
                },
            ).execute()
            return raspuns.data

        return await to_thread.run_sync(interogare)

    async def ramburseaza_anticipat(
        self,
        id_credit: UUID,
        principal_platit: float,
        dobanda_acumulata: float = 0.0,
        grafic_nou: list[dict] | None = None,
    ) -> dict:
        def interogare() -> dict:
            raspuns = self._client.rpc(
                "credit_ramburseaza_anticipat",
                {
                    "p_id_credit": str(id_credit),
                    "p_principal_platit": principal_platit,
                    "p_dobanda_acumulata": dobanda_acumulata,
                    "p_grafic_nou": grafic_nou,
                },
            ).execute()
            return raspuns.data

        return await to_thread.run_sync(interogare)
