"""CreditAiPipeline — strict consultativ, tolerant la esec, idempotent prin hash.

Repository si provider sunt falsuri in memorie: nu se testeaza Supabase sau
Foundry aici (asta e treaba verificarii live, REGULI.md #7), ci comportamentul
pipeline-ului — ce se intampla cand o etapa lipseste, esueaza, sau cand datele
nu s-au schimbat fata de ultima rulare.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.credit.ai.contracte import DatePipelineCredit
from app.credit.ai.pipeline import CreditAiPipeline
from app.providers.base import StructuredCompletion

ID_CERERE = uuid4()
CREAT_LA = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc).isoformat()


def _date_pipeline(
    status: str = "analiza_manuala", cu_document: bool = True, sursa: str = "text"
) -> DatePipelineCredit:
    documente = [{
        "id": str(uuid4()), "hash_fisier": "abc123", "status": "procesat", "creat_la": CREAT_LA,
        "extras": {
            "text": "Adeverinta de venit, salariu net 5000 lei.",
            "venit_net": "5000",
            "sursa": sursa,
        },
    }] if cu_document else []
    return DatePipelineCredit(
        cerere={
            "id": str(ID_CERERE), "status": status, "venit_declarat": "5000", "angajator": None,
            "obligatii_declarate": "0", "venit_folosit": "5000", "scor": 55, "dti": "0.2",
            "motive": [{"cod": "dti", "puncte": 20, "maxim": 30, "explicatie": "ok"}],
            "creat_la": CREAT_LA,
        },
        documente=documente, documente_reutilizate=[], verificari=[], venit_constatat=None, plati=[],
    )


class _CreditServiceFals:
    def __init__(self, date: DatePipelineCredit | None = None, arunca: bool = False) -> None:
        self._date = date
        self._arunca = arunca
        self.apeluri = 0

    async def date_pentru_pipeline(self, id_cerere):
        self.apeluri += 1
        if self._arunca:
            raise RuntimeError("repository picat")
        return self._date


class _RepoFals:
    def __init__(self) -> None:
        self.rulari: list[dict] = []
        self.etape: list[dict] = []
        self.semnale_salvate: list = []

    async def rulare_recenta(self, id_cerere):
        potrivite = [r for r in self.rulari if r["id_cerere"] == str(id_cerere)]
        return potrivite[-1] if potrivite else None

    async def creeaza_rulare(self, id_cerere, declansator, versiune_pipeline, intrare_hash) -> dict:
        rand = {
            "id": str(uuid4()), "id_cerere": str(id_cerere), "declansator": declansator,
            "versiune_pipeline": versiune_pipeline, "intrare_hash": intrare_hash, "status": "in_curs",
            "recomandare": None, "incredere": None, "latenta_ms": None, "cost_estimat_usd": 0,
            "creat_la": CREAT_LA, "finalizat_la": None,
        }
        self.rulari.append(rand)
        return rand

    async def finalizeaza_rulare(
        self, id_rulare, *, status, recomandare=None, incredere=None,
        latenta_ms=0, cost_estimat_usd=0.0,
    ) -> dict:
        for rand in self.rulari:
            if rand["id"] == str(id_rulare):
                rand.update(status=status, recomandare=recomandare, incredere=incredere,
                            latenta_ms=latenta_ms, cost_estimat_usd=cost_estimat_usd)
                return rand
        raise AssertionError("rulare inexistenta")

    async def salveaza_etapa(self, id_rulare, campuri: dict) -> dict:
        rand = {"id_rulare": str(id_rulare), **campuri}
        self.etape.append(rand)
        return rand

    async def salveaza_semnale(self, id_cerere, id_rulare, semnale) -> None:
        self.semnale_salvate.extend(semnale)

    def etapa(self, nume: str) -> dict | None:
        potrivite = [e for e in self.etape if e["etapa"] == nume]
        return potrivite[-1] if potrivite else None


class _ProviderFals:
    deployment = "model-fals"

    def __init__(self, raspunsuri: dict | None = None, arunca_pe: frozenset[str] = frozenset()) -> None:
        self._raspunsuri = raspunsuri or {}
        self._arunca_pe = arunca_pe
        self.apeluri: list[str] = []

    async def complete_json(self, messages, schema_name: str, schema: dict) -> StructuredCompletion:
        self.apeluri.append(schema_name)
        if schema_name in self._arunca_pe:
            raise RuntimeError(f"modelul a picat pe {schema_name}")
        date = self._raspunsuri.get(schema_name, {})
        return StructuredCompletion(data=date, tokens_in=10, tokens_out=10, tokens_cached=0, deployment=self.deployment)


class _RetrievalFals:
    async def search(self, query, profile=None):
        return []


_RASPUNSURI_VALIDE = {
    "extractie_adeverinta": {
        "venit_net": 5000, "venit_brut": None, "angajator": "ACME SRL", "cui_angajator": None,
        "perioada": None, "functie": None, "are_stampila": True, "are_semnatura": True,
        "incredere": 0.9, "citate": {"venit_net": "salariu net 5000 lei", "angajator": None},
    },
    "brief_analist": {
        "rezumat": "Dosar echilibrat.", "riscuri": [], "atenuari": [], "intrebari_de_pus": [],
        "recomandare": "aproba", "incredere": 0.7, "citate": [],
    },
}


def _pipeline(provider=None, repo: _RepoFals | None = None, credit_service=None, retrieval=None) -> tuple[CreditAiPipeline, _RepoFals]:
    repo = repo or _RepoFals()
    credit_service = credit_service or _CreditServiceFals(_date_pipeline())
    return CreditAiPipeline(
        credit_service=credit_service, repository=repo, structured_provider=provider,
        retrieval_service=retrieval, environment="test", price_per_million_in=0.0, price_per_million_out=0.0,
    ), repo


async def test_fara_provider_coerenta_ruleaza_restul_sar() -> None:
    pipeline, repo = _pipeline(provider=None, retrieval=None)

    rulare = await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert rulare["status"] == "finalizat"
    assert rulare["recomandare"] is None
    assert repo.etapa("documente")["status"] == "sarit"
    assert repo.etapa("coerenta")["status"] == "reusit"
    assert repo.etapa("brief")["status"] == "sarit"


async def test_documentul_citit_din_tabel_nu_mai_trece_pe_la_model() -> None:
    """Cand Azure a citit direct coloana „Venit Net", modelul n-are ce adauga.

    Nu e o optimizare de tokeni, ci de claritate: pana acum analistul primea
    doua panouri cu aceeasi cifra, iar cifra modelului o BATEA pe cea din
    coloana in `coerenta._venit_document` — o parafraza care castiga in fata
    unui antet de tabel. Motivul se scrie in etapa, ca sa se vada in pagina de
    observabilitate ca a fost o decizie, nu o pana.
    """
    provider = _ProviderFals(_RASPUNSURI_VALIDE)
    pipeline, repo = _pipeline(
        provider=provider,
        credit_service=_CreditServiceFals(_date_pipeline(sursa="tabel")),
        retrieval=_RetrievalFals(),
    )

    rulare = await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert repo.etapa("documente")["status"] == "sarit"
    assert repo.etapa("documente")["cod_eroare"] == "citit_din_tabel"
    # Restul pipeline-ului merge mai departe pe cifra din `extras`.
    assert repo.etapa("coerenta")["status"] == "reusit"
    assert rulare["status"] == "finalizat"


async def test_documentul_citit_din_text_trece_pe_la_model() -> None:
    """Pe adeverintele scrise curgator prima citire e o potrivire de
    vecinatate, deci a doua parere inca merita platita."""
    provider = _ProviderFals(_RASPUNSURI_VALIDE)
    pipeline, repo = _pipeline(
        provider=provider,
        credit_service=_CreditServiceFals(_date_pipeline(sursa="text")),
        retrieval=_RetrievalFals(),
    )

    await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert repo.etapa("documente")["status"] == "reusit"


async def test_cu_provider_documente_si_brief_reusesc() -> None:
    provider = _ProviderFals(_RASPUNSURI_VALIDE)
    pipeline, repo = _pipeline(provider=provider, retrieval=_RetrievalFals())

    rulare = await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert rulare["status"] == "finalizat"
    assert rulare["recomandare"] == "aproba"
    assert repo.etapa("documente")["status"] == "reusit"
    assert repo.etapa("documente")["rezultat"]["venit_net"] == "5000"
    assert repo.etapa("brief")["status"] == "reusit"


async def test_o_etapa_esuata_nu_opreste_pipeline_ul() -> None:
    provider = _ProviderFals(_RASPUNSURI_VALIDE, arunca_pe=frozenset({"extractie_adeverinta"}))
    pipeline, repo = _pipeline(provider=provider, retrieval=_RetrievalFals())

    rulare = await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert rulare["status"] == "finalizat"
    assert repo.etapa("documente")["status"] == "esuat"
    assert repo.etapa("documente")["cod_eroare"] == "RuntimeError"
    # brief tot a rulat, independent de documente:
    assert repo.etapa("brief")["status"] == "reusit"
    assert rulare["recomandare"] == "aproba"


async def test_status_diferit_de_analiza_manuala_sare_brief() -> None:
    date = _date_pipeline(status="oferta")
    provider = _ProviderFals(_RASPUNSURI_VALIDE)
    pipeline, repo = _pipeline(provider=provider, retrieval=_RetrievalFals(), credit_service=_CreditServiceFals(date))

    rulare = await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert repo.etapa("brief")["status"] == "sarit"
    assert repo.etapa("brief")["cod_eroare"] == "cererea_nu_e_in_analiza_manuala"
    assert rulare["recomandare"] is None


async def test_rulare_neschimbata_se_refoloseste() -> None:
    provider = _ProviderFals(_RASPUNSURI_VALIDE)
    pipeline, repo = _pipeline(provider=provider, retrieval=_RetrievalFals())

    intaia = await pipeline.ruleaza(ID_CERERE, "evalueaza")
    a_doua = await pipeline.ruleaza(ID_CERERE, "lazy")

    assert intaia["id"] == a_doua["id"]
    assert len(repo.rulari) == 1
    assert provider.apeluri.count("extractie_adeverinta") == 1


async def test_forta_recheama_chiar_daca_hash_neschimbat() -> None:
    provider = _ProviderFals(_RASPUNSURI_VALIDE)
    pipeline, repo = _pipeline(provider=provider, retrieval=_RetrievalFals())

    await pipeline.ruleaza(ID_CERERE, "evalueaza")
    await pipeline.ruleaza(ID_CERERE, "manual", forta=True)

    assert len(repo.rulari) == 2
    assert provider.apeluri.count("extractie_adeverinta") == 2


async def test_esec_neasteptat_nu_darama_apelantul() -> None:
    pipeline, _ = _pipeline(credit_service=_CreditServiceFals(None, arunca=True))

    rezultat = await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert rezultat is None


async def test_esecul_de_dupa_creare_marcheaza_rularea_esuata() -> None:
    """Regresie: rularile picate ramaneau 'in_curs' pentru totdeauna.

    `finalizeaza_rulare` era chemat intr-un singur loc, mereu cu 'finalizat',
    deci valoarea 'esuat' din constrangerea migratiei 0018 nu o scria nimeni.
    Efectul se vedea in dashboard: dosarul arata un panou gol permanent, fiindca
    `dosar_ai` lua ultima rulare indiferent de status.
    """
    repo = _RepoFals()

    async def pica(id_cerere, id_rulare, semnale) -> None:
        raise RuntimeError("baza a picat dupa ce rularea a fost deschisa")

    repo.salveaza_semnale = pica  # type: ignore[method-assign]
    pipeline, _ = _pipeline(repo=repo)

    assert await pipeline.ruleaza(ID_CERERE, "evalueaza") is None

    assert len(repo.rulari) == 1
    assert repo.rulari[0]["status"] == "esuat"


async def test_fara_retrieval_briefu_spune_care_e_cauza() -> None:
    """`fara_provider` pentru o lipsa de retrieval trimitea pe cine se uita in
    pagina de observabilitate direct catre configuratia Foundry — alta cauza."""
    pipeline, repo = _pipeline(provider=_ProviderFals(_RASPUNSURI_VALIDE), retrieval=None)

    await pipeline.ruleaza(ID_CERERE, "evalueaza")

    assert repo.etapa("brief")["cod_eroare"] == "fara_retrieval"
