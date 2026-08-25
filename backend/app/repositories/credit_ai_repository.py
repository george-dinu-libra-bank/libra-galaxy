"""Accesul la datele pipeline-ului AI de credite (0018_credit_ai_pipeline.sql).

Acelasi tipar ca CreditRepository: clientul e cel cu service_role (tabelele
credit_ai_* nu au nicio politica pentru 'authenticated' — vezi migratia),
metodele sunt async si impacheteaza supabase-py in `to_thread.run_sync`.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from anyio import to_thread
from supabase import Client

from app.credit.ai.contracte import Semnal


class CreditAiRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    # -- rulari ---------------------------------------------------------

    async def creeaza_rulare(
        self, id_cerere: UUID, declansator: str, versiune_pipeline: str, intrare_hash: str
    ) -> dict:
        def interogare() -> dict:
            raspuns = (
                self._client.table("credit_ai_rulari")
                .insert({
                    "id_cerere": str(id_cerere), "declansator": declansator,
                    "versiune_pipeline": versiune_pipeline, "intrare_hash": intrare_hash,
                    "status": "in_curs",
                })
                .execute()
            )
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    async def rulare_recenta(self, id_cerere: UUID) -> dict | None:
        """Ultima rulare (orice status), pentru catch-up lazy: daca hash-ul de
        intrare nu s-a schimbat si a reusit, nu se recheama modelul."""
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("credit_ai_rulari")
                .select("*")
                .eq("id_cerere", str(id_cerere))
                .order("creat_la", desc=True)
                .limit(1)
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        return await to_thread.run_sync(interogare)

    async def finalizeaza_rulare(
        self, id_rulare: UUID, *, status: str, recomandare: str | None = None,
        incredere: float | None = None, latenta_ms: int = 0, cost_estimat_usd: float = 0.0,
    ) -> dict:
        """Inchide o rulare — reusita sau esuata.

        Implicitele exista pentru al doilea caz: o rulare care a picat n-are nici
        recomandare, nici incredere, iar apelantul (`CreditAiPipeline.ruleaza`)
        n-are de unde sti latenta unei cai care s-a rupt la mijloc.
        """
        def interogare() -> dict:
            from datetime import datetime, timezone

            raspuns = (
                self._client.table("credit_ai_rulari")
                .update({
                    "status": status, "recomandare": recomandare, "incredere": incredere,
                    "latenta_ms": latenta_ms, "cost_estimat_usd": cost_estimat_usd,
                    "finalizat_la": datetime.now(timezone.utc).isoformat(),
                })
                .eq("id", str(id_rulare))
                .execute()
            )
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    # -- etape ------------------------------------------------------------

    async def salveaza_etapa(self, id_rulare: UUID, campuri: dict[str, Any]) -> dict:
        def interogare() -> dict:
            raspuns = (
                self._client.table("credit_ai_etape")
                .insert({"id_rulare": str(id_rulare), **campuri})
                .execute()
            )
            return raspuns.data[0]

        return await to_thread.run_sync(interogare)

    async def etape(self, id_rulare: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_ai_etape")
                .select("*")
                .eq("id_rulare", str(id_rulare))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    # -- semnale ------------------------------------------------------------

    async def salveaza_semnale(self, id_cerere: UUID, id_rulare: UUID, semnale: list[Semnal]) -> None:
        if not semnale:
            return

        def interogare() -> None:
            self._client.table("credit_ai_semnale").insert([
                {
                    "id_cerere": str(id_cerere), "id_rulare": str(id_rulare),
                    "cod": semnal.cod, "severitate": semnal.severitate, "titlu": semnal.titlu,
                    "detaliu": semnal.detaliu, "sursa": semnal.sursa,
                }
                for semnal in semnale
            ]).execute()

        await to_thread.run_sync(interogare)

    async def semnale(self, id_rulare: UUID) -> list[dict]:
        def interogare() -> list[dict]:
            raspuns = (
                self._client.table("credit_ai_semnale")
                .select("*")
                .eq("id_rulare", str(id_rulare))
                .order("creat_la")
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def semnale_grupate(self, id_cereri: list[UUID]) -> dict[str, dict]:
        """Numarul de semnale grave/atentie din ULTIMA rulare finalizata a
        fiecarei cereri — pentru badge-urile din lista (lista-cereri-credit.tsx).

        Doua interogari, nu un join: supabase-py nu are subselect corelat, deci
        se afla intai cea mai recenta rulare per cerere, apoi semnalele ei.
        """
        if not id_cereri:
            return {}

        def interogare_rulari() -> list[dict]:
            raspuns = (
                self._client.table("credit_ai_rulari")
                .select("id,id_cerere,creat_la")
                .in_("id_cerere", [str(i) for i in id_cereri])
                .eq("status", "finalizat")
                .order("creat_la", desc=True)
                .execute()
            )
            return raspuns.data or []

        rulari = await to_thread.run_sync(interogare_rulari)
        rulare_curenta_per_cerere: dict[str, str] = {}
        for rand in rulari:
            rulare_curenta_per_cerere.setdefault(str(rand["id_cerere"]), str(rand["id"]))
        if not rulare_curenta_per_cerere:
            return {}

        def interogare_semnale() -> list[dict]:
            raspuns = (
                self._client.table("credit_ai_semnale")
                .select("id_rulare,severitate")
                .in_("id_rulare", list(rulare_curenta_per_cerere.values()))
                .execute()
            )
            return raspuns.data or []

        semnale = await to_thread.run_sync(interogare_semnale)
        rulare_catre_cerere = {v: k for k, v in rulare_curenta_per_cerere.items()}

        rezultat: dict[str, dict] = {}
        for rand in semnale:
            id_cerere = rulare_catre_cerere.get(str(rand["id_rulare"]))
            if id_cerere is None:
                continue
            agregat = rezultat.setdefault(id_cerere, {"grave": 0, "atentie": 0, "informativ": 0})
            cheie = {"grav": "grave", "atentie": "atentie", "informativ": "informativ"}[rand["severitate"]]
            agregat[cheie] += 1
        return rezultat

    # -- dosarul complet (pentru panoul din /admin/credite/{id}) ------------

    async def rulare_de_aratat(self, id_cerere: UUID) -> dict | None:
        """Ultima rulare pe care are rost sa o vada un analist.

        Nu neaparat cea mai recenta: o rulare ramasa 'in_curs' (proces repornit,
        esec inainte de a fi inchisa) sau una 'esuat' n-are nici semnale, nici
        brief, deci ar ascunde in spatele unui panou gol ultimul rezultat bun.
        Se prefera ultima finalizata; daca nu exista niciuna, se arata ultima
        oricare, ca panoul sa poata spune ce s-a intamplat.
        """
        def interogare() -> dict | None:
            raspuns = (
                self._client.table("credit_ai_rulari")
                .select("*")
                .eq("id_cerere", str(id_cerere))
                .eq("status", "finalizat")
                .order("creat_la", desc=True)
                .limit(1)
                .maybe_single()
                .execute()
            )
            return raspuns.data if raspuns else None

        finalizata = await to_thread.run_sync(interogare)
        return finalizata if finalizata is not None else await self.rulare_recenta(id_cerere)

    async def dosar_ai(self, id_cerere: UUID) -> dict | None:
        rulare = await self.rulare_de_aratat(id_cerere)
        if rulare is None:
            return None
        id_rulare = UUID(rulare["id"])
        etape, semnale = await asyncio.gather(self.etape(id_rulare), self.semnale(id_rulare))
        return {"rulare": rulare, "etape": etape, "semnale": semnale}

    # -- observabilitate ------------------------------------------------------

    async def rezumat_zilnic(self, zile: int = 30) -> list[dict]:
        def interogare() -> list[dict]:
            from datetime import datetime, timedelta, timezone

            de_la = (datetime.now(timezone.utc) - timedelta(days=zile)).date().isoformat()
            raspuns = (
                self._client.table("credit_ai_rezumat_zilnic")
                .select("*")
                .gte("zi", de_la)
                .order("zi", desc=True)
                .execute()
            )
            return raspuns.data or []

        return await to_thread.run_sync(interogare)

    async def rata_acord(self) -> dict:
        """Rata de acord AI vs. decizia finala a omului — din view-ul
        credit_ai_acord. Agregat aici, nu in SQL: la scara acestei banci demo,
        cateva sute de randuri cel mult, nu merita inca o vizualizare."""
        def interogare() -> list[dict]:
            raspuns = self._client.table("credit_ai_acord").select("de_acord").execute()
            return raspuns.data or []

        randuri = await to_thread.run_sync(interogare)
        comparabile = [r for r in randuri if r["de_acord"] is not None]
        de_acord = sum(1 for r in comparabile if r["de_acord"])
        return {
            "total_comparabile": len(comparabile),
            "de_acord": de_acord,
            "rata": round(de_acord / len(comparabile), 3) if comparabile else None,
        }

    async def cost_recent(self, zile: int = 30) -> float:
        """Costul estimat al pipeline-ului, ultimele `zile` zile.

        Doua surse: `credit_ai_rulari.cost_estimat_usd` acopera etapele 1-3
        (documente, brief); etapa 4 (explicatie) ruleaza sincron in
        credit_service.evalueaza() si isi scrie costul direct in
        `ai_usage_records` (feature='credit_pipeline') — vezi
        app/credit/ai/etape/explicatie.py.
        """
        def interogare() -> tuple[list[dict], list[dict]]:
            from datetime import datetime, timedelta, timezone

            de_la = (datetime.now(timezone.utc) - timedelta(days=zile)).isoformat()
            rulari = (
                self._client.table("credit_ai_rulari").select("cost_estimat_usd")
                .gte("creat_la", de_la).eq("status", "finalizat").execute()
            )
            explicatii = (
                self._client.table("ai_usage_records").select("cost_estimat_usd")
                .gte("produs_la", de_la).eq("feature", "credit_pipeline").execute()
            )
            return rulari.data or [], explicatii.data or []

        rulari, explicatii = await to_thread.run_sync(interogare)
        return round(
            sum(float(r["cost_estimat_usd"] or 0) for r in rulari)
            + sum(float(e["cost_estimat_usd"] or 0) for e in explicatii),
            6,
        )
