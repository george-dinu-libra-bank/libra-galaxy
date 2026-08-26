"""CreditAiPipeline — compune etapele 1-3 (documente, coerenta, brief).

Etapa 4 (explicatie) NU e aici: ruleaza sincron in `credit_service.evalueaza()`
prin hook-ul `explica=` (vezi `etape/explicatie.py`) — trebuie sa fie gata
inainte sa raspunda ruta, deci nu poate fi o rulare de fundal.

Principii (vezi planul din memoria de sesiune / docs/AGENTS.md):

- **Strict consultativ.** Nimic de aici nu scrie in credit_cereri, scor, dti
  sau credit_verificari_venit.
- **Nu poate darama fluxul.** Fiecare etapa e izolata: o exceptie in una nu
  opreste celelalte, se marcheaza 'esuat' si pipeline-ul continua.
- **Idempotent prin hash.** O rulare reusita cu acelasi `intrare_hash` se
  refoloseste — deschiderea repetata a unui dosar nu recheama modelul.
"""

from __future__ import annotations

import json
import logging
import time
from hashlib import sha256
from uuid import UUID

from app.credit.ai import prompturi
from app.credit.ai.contracte import DatePipelineCredit, ExtractieDocument, Semnal
from app.credit.ai.etape import brief as etapa_brief
from app.credit.ai.etape import coerenta as etapa_coerenta
from app.credit.ai.etape import documente as etapa_documente
from app.providers.base import StructuredChatProvider
from app.rag.retrieval import RetrievalService
from app.repositories.credit_ai_repository import CreditAiRepository
from app.services.credit_service import CreditService
from app.telemetry.metrics import estimate_chat_cost

logger = logging.getLogger(__name__)

VERSIUNE_PIPELINE = "credit-ai-v1"

# 'analiza_manuala' e singurul status in care un om chiar citeste un brief ca
# sa decida — restul (oferta emisa, respins pe criterii hard, ciorna) n-au ce
# face cu o recomandare pe care nimeni n-o cere.
STATUSURI_CU_BRIEF = frozenset({"analiza_manuala"})

_VERDICT_DUPA_STATUS = {"oferta": "aprobat", "respinsa": "respins", "analiza_manuala": "analiza_manuala"}


class CreditAiPipeline:
    def __init__(
        self,
        *,
        credit_service: CreditService,
        repository: CreditAiRepository,
        structured_provider: StructuredChatProvider | None,
        retrieval_service: RetrievalService | None,
        environment: str,
        price_per_million_in: float,
        price_per_million_out: float,
        max_semnale: int = 20,
    ) -> None:
        self._credite = credit_service
        self._depozit = repository
        self._provider = structured_provider
        self._retrieval = retrieval_service
        self._environment = environment
        self._price_in = price_per_million_in
        self._price_out = price_per_million_out
        self._max_semnale = max_semnale

    async def ruleaza(self, id_cerere: UUID, declansator: str, *, forta: bool = False) -> dict | None:
        """Punctul de intrare unic — chemat din rute, ca task de fundal, sau
        lazy la deschiderea dosarului. Nu arunca niciodata: un esec aici nu are
        voie sa darame ruta care l-a declansat.

        `forta=True` sare peste refolosirea prin hash — butonul "Ruleaza din
        nou" din dashboard trebuie sa recheme efectiv modelul, nu sa intoarca
        acelasi rezultat din cache.
        """
        # `id_rulare` iese din `_ruleaza` prin lista asta fiindca randul se
        # creeaza inauntru, iar cand ceva pica dupa crearea lui trebuie inchis
        # de aici. Fara asta, orice esec lasa o rulare 'in_curs' pentru
        # totdeauna: dosarul arata un panou gol permanent, iar valoarea 'esuat'
        # din constrangerea migratiei 0018 nu era scrisa de nimeni, niciodata.
        deschisa: list[UUID] = []
        try:
            return await self._ruleaza(id_cerere, declansator, forta=forta, deschisa=deschisa)
        except Exception:
            logger.exception("pipeline AI credite: esec neasteptat pentru cererea %s", id_cerere)
            for id_rulare in deschisa:
                try:
                    await self._depozit.finalizeaza_rulare(id_rulare, status="esuat")
                except Exception:
                    # Daca nici marcarea nu merge, baza e oricum indisponibila.
                    # Nu inlocuim exceptia originala cu asta.
                    logger.exception("pipeline AI credite: nu am putut marca rularea %s ca esuata", id_rulare)
            return None

    async def _ruleaza(
        self, id_cerere: UUID, declansator: str, *, forta: bool, deschisa: list[UUID]
    ) -> dict:
        date = await self._credite.date_pentru_pipeline(id_cerere)
        intrare_hash = _hash_intrare(date)

        if not forta:
            ultima = await self._depozit.rulare_recenta(id_cerere)
            if ultima is not None and ultima.get("intrare_hash") == intrare_hash and ultima.get("status") == "finalizat":
                return ultima

        inceput = time.perf_counter()
        rulare = await self._depozit.creeaza_rulare(id_cerere, declansator, VERSIUNE_PIPELINE, intrare_hash)
        id_rulare = UUID(rulare["id"])
        deschisa.append(id_rulare)

        extractie, cost_documente = await self._ruleaza_documente(id_rulare, date)

        semnale, cost_coerenta = await self._ruleaza_coerenta(id_rulare, date, extractie)
        await self._depozit.salveaza_semnale(id_cerere, id_rulare, _plafoneaza(semnale, self._max_semnale))

        recomandare, incredere_brief, cost_brief = await self._ruleaza_brief(id_rulare, date, semnale)

        latenta_ms = int((time.perf_counter() - inceput) * 1000)
        return await self._depozit.finalizeaza_rulare(
            id_rulare, status="finalizat", recomandare=recomandare, incredere=incredere_brief,
            latenta_ms=latenta_ms, cost_estimat_usd=round(cost_documente + cost_coerenta + cost_brief, 6),
        )

    # -- etapa 1: documente ---------------------------------------------

    async def _ruleaza_documente(
        self, id_rulare: UUID, date: DatePipelineCredit
    ) -> tuple[ExtractieDocument | None, float]:
        text = _text_document(date.documente)
        if self._provider is None or text is None:
            await self._depozit.salveaza_etapa(id_rulare, {
                "etapa": "documente", "status": "sarit",
                "versiune_prompt": prompturi.VERSIUNE_DOCUMENTE,
                "cod_eroare": "fara_provider" if self._provider is None else "fara_document",
            })
            return None, 0.0

        inceput = time.perf_counter()
        try:
            rezultat = await etapa_documente.ruleaza(self._provider, text)
        except Exception as exc:
            logger.warning("etapa 'documente' a esuat pentru rularea %s: %s", id_rulare, exc)
            await self._depozit.salveaza_etapa(id_rulare, {
                "etapa": "documente", "status": "esuat", "versiune_prompt": prompturi.VERSIUNE_DOCUMENTE,
                "cod_eroare": type(exc).__name__, "latenta_ms": _ms_de_la(inceput),
            })
            return None, 0.0

        cost = estimate_chat_cost(rezultat.tokens_in, rezultat.tokens_out, self._price_in, self._price_out)
        await self._depozit.salveaza_etapa(id_rulare, {
            "etapa": "documente", "status": "reusit", "versiune_prompt": prompturi.VERSIUNE_DOCUMENTE,
            "deployment": rezultat.deployment, "rezultat": _extractie_ca_dict(rezultat.extractie),
            "incredere": rezultat.extractie.incredere, "latenta_ms": _ms_de_la(inceput),
            "tokeni_intrare": rezultat.tokens_in, "tokeni_iesire": rezultat.tokens_out,
            "tokeni_cache": rezultat.tokens_cached,
        })
        return rezultat.extractie, cost

    # -- etapa 2: coerenta ------------------------------------------------

    async def _ruleaza_coerenta(
        self, id_rulare: UUID, date: DatePipelineCredit, extractie: ExtractieDocument | None
    ) -> tuple[list[Semnal], float]:
        inceput = time.perf_counter()
        try:
            semnale = etapa_coerenta.evalueaza(
                cerere=date.cerere, documente=date.documente,
                documente_reutilizate=date.documente_reutilizate,
                venit_constatat=date.venit_constatat, plati=date.plati,
                extractie_document=extractie,
            )
        except Exception as exc:
            # N-ar trebui sa se intample niciodata — e determinista si pura.
            # Orice aparitie de aici e un bug in coerenta.py, nu o problema de
            # infrastructura (asa se distinge pe pagina de observabilitate).
            logger.exception("etapa 'coerenta' a esuat pentru rularea %s (bug, nu infra)", id_rulare)
            await self._depozit.salveaza_etapa(id_rulare, {
                "etapa": "coerenta", "status": "esuat", "cod_eroare": type(exc).__name__,
                "latenta_ms": _ms_de_la(inceput),
            })
            return [], 0.0

        await self._depozit.salveaza_etapa(id_rulare, {
            "etapa": "coerenta", "status": "reusit",
            "rezultat": {"coduri": [s.cod for s in semnale]}, "latenta_ms": _ms_de_la(inceput),
        })
        return semnale, 0.0

    # -- etapa 3: brief -----------------------------------------------------

    async def _ruleaza_brief(
        self, id_rulare: UUID, date: DatePipelineCredit, semnale: list[Semnal]
    ) -> tuple[str | None, float | None, float]:
        if date.cerere.get("status") not in STATUSURI_CU_BRIEF:
            await self._depozit.salveaza_etapa(id_rulare, {
                "etapa": "brief", "status": "sarit", "versiune_prompt": prompturi.VERSIUNE_BRIEF,
                "cod_eroare": "cererea_nu_e_in_analiza_manuala",
            })
            return None, None, 0.0
        if self._provider is None or self._retrieval is None:
            # Doua cauze diferite, doua coduri diferite: pagina de observabilitate
            # arata "de ce n-a rulat", iar "fara_provider" pentru o lipsa de
            # retrieval trimitea pe cine se uita direct catre configuratia Foundry.
            await self._depozit.salveaza_etapa(id_rulare, {
                "etapa": "brief", "status": "sarit", "versiune_prompt": prompturi.VERSIUNE_BRIEF,
                "cod_eroare": "fara_provider" if self._provider is None else "fara_retrieval",
            })
            return None, None, 0.0

        inceput = time.perf_counter()
        motive, factori = _motive_si_factori(date.cerere)
        try:
            context = await etapa_brief.construieste_context(
                cerere=date.cerere,
                verdict=_VERDICT_DUPA_STATUS.get(str(date.cerere.get("status")), str(date.cerere.get("status"))),
                scor=date.cerere.get("scor"), dti=date.cerere.get("dti"),
                motive=motive, factori=factori, verificari=date.verificari,
                semnale=semnale, retrieval=self._retrieval,
            )
            rezultat = await etapa_brief.ruleaza(self._provider, context)
        except Exception as exc:
            logger.warning("etapa 'brief' a esuat pentru rularea %s: %s", id_rulare, exc)
            await self._depozit.salveaza_etapa(id_rulare, {
                "etapa": "brief", "status": "esuat", "versiune_prompt": prompturi.VERSIUNE_BRIEF,
                "cod_eroare": type(exc).__name__, "latenta_ms": _ms_de_la(inceput),
            })
            return None, None, 0.0

        cost = estimate_chat_cost(rezultat.tokens_in, rezultat.tokens_out, self._price_in, self._price_out)
        await self._depozit.salveaza_etapa(id_rulare, {
            "etapa": "brief", "status": "reusit", "versiune_prompt": prompturi.VERSIUNE_BRIEF,
            "deployment": rezultat.deployment, "rezultat": _brief_ca_dict(rezultat.brief),
            "incredere": rezultat.brief.incredere, "latenta_ms": _ms_de_la(inceput),
            "tokeni_intrare": rezultat.tokens_in, "tokeni_iesire": rezultat.tokens_out,
            "tokeni_cache": rezultat.tokens_cached,
        })
        return rezultat.brief.recomandare, rezultat.brief.incredere, cost


_ORDINE_SEVERITATE = {"grav": 0, "atentie": 1, "informativ": 2}


def _plafoneaza(semnale: list[Semnal], maxim: int) -> list[Semnal]:
    """O coeruptie neasteptata a tranzactiilor n-are voie sa scrie mii de
    randuri — se pastreaza cele mai severe."""
    if len(semnale) <= maxim:
        return semnale
    return sorted(semnale, key=lambda s: _ORDINE_SEVERITATE.get(s.severitate, 9))[:maxim]


def _ms_de_la(inceput: float) -> int:
    return int((time.perf_counter() - inceput) * 1000)


def _text_document(documente: list[dict]) -> str | None:
    """Textul brut al ultimei adeverinte inca prezente — deja salvat la
    incarcare (`extras.text`), nu se reciteste fisierul din storage."""
    for document in sorted(documente, key=lambda d: str(d.get("creat_la", "")), reverse=True):
        if document.get("sters_la"):
            continue
        text = (document.get("extras") or {}).get("text")
        if text:
            return text
    return None


def _motive_si_factori(cerere: dict) -> tuple[list[dict], list[dict]]:
    """Coloana `motive` tine si motivele de respingere hard, si factorii
    scorecard-ului — se disting dupa 'maxim' (acelasi tipar ca in frontend,
    lista-cereri-credit.tsx / admin/credite/[id]/page.tsx)."""
    elemente = cerere.get("motive") or []
    factori = [e for e in elemente if isinstance(e, dict) and "maxim" in e]
    motive = [e for e in elemente if isinstance(e, dict) and "maxim" not in e]
    return motive, factori


def _extractie_ca_dict(extractie: ExtractieDocument) -> dict:
    return {
        "venit_net": str(extractie.venit_net) if extractie.venit_net is not None else None,
        "venit_brut": str(extractie.venit_brut) if extractie.venit_brut is not None else None,
        "angajator": extractie.angajator,
        "cui_angajator": extractie.cui_angajator,
        "perioada": extractie.perioada,
        "functie": extractie.functie,
        "are_stampila": extractie.are_stampila,
        "are_semnatura": extractie.are_semnatura,
        "incredere": extractie.incredere,
        "citate": extractie.citate,
    }


def _brief_ca_dict(brief) -> dict:
    return {
        "rezumat": brief.rezumat,
        "riscuri": brief.riscuri,
        "atenuari": brief.atenuari,
        "intrebari_de_pus": brief.intrebari_de_pus,
        "recomandare": brief.recomandare,
        "incredere": brief.incredere,
        "citate": [{"document_id": c.document_id, "text": c.text} for c in brief.citate],
    }


def _hash_intrare(date: DatePipelineCredit) -> str:
    """sha256 peste tot ce ar putea schimba rezultatul unei rulari — daca nimic
    de-aici nu s-a schimbat fata de ultima rulare reusita, se refoloseste."""
    incarcatura = {
        "cerere": {
            cheie: str(date.cerere.get(cheie))
            for cheie in ("status", "venit_declarat", "angajator", "obligatii_declarate",
                          "venit_folosit", "scor", "dti", "motive")
        },
        "documente": sorted(
            (str(d.get("hash_fisier") or d.get("id")), str(d.get("status"))) for d in date.documente
        ),
        "documente_reutilizate": sorted(str(d.get("id")) for d in date.documente_reutilizate),
        "venit_constatat": (
            [round(date.venit_constatat.venit_lunar, 2), date.venit_constatat.platitor]
            if date.venit_constatat else None
        ),
    }
    bruta = json.dumps(incarcatura, sort_keys=True, default=str, ensure_ascii=False)
    return sha256(bruta.encode("utf-8")).hexdigest()
