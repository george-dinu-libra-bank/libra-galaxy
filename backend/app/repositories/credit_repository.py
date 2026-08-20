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

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from anyio import to_thread
from supabase import Client

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
