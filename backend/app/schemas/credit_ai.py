"""Contractele HTTP pentru pipeline-ul AI de credite (zona de administrare).

Nimic de aici nu e expus clientului: rutele care le folosesc traiesc sub
`router_admin` din api/routes/credite.py, in spatele lui `cere_administrator`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SemnalResponse(BaseModel):
    cod: str
    severitate: str
    titlu: str
    detaliu: dict = Field(default_factory=dict)
    sursa: str


class SemnaleRezumatResponse(BaseModel):
    """Numarul de semnale din ultima rulare, pentru badge-ul din lista de cereri."""

    grave: int = 0
    atentie: int = 0
    informativ: int = 0


class EtapaAiResponse(BaseModel):
    etapa: str
    status: str
    versiune_prompt: str | None = None
    deployment: str | None = None
    rezultat: dict = Field(default_factory=dict)
    incredere: float | None = None
    latenta_ms: int | None = None
    cod_eroare: str | None = None
    creat_la: str


class RulareAiResponse(BaseModel):
    id: str
    status: str
    declansator: str
    versiune_pipeline: str
    recomandare: str | None = None
    incredere: float | None = None
    latenta_ms: int | None = None
    cost_estimat_usd: float | None = None
    creat_la: str
    finalizat_la: str | None = None


class DosarAiResponse(BaseModel):
    """Panoul din dosarul cererii — ultima rulare, etapele ei, semnalele ei."""

    rulare: RulareAiResponse
    etape: list[EtapaAiResponse]
    semnale: list[SemnalResponse]


# -----------------------------------------------------------------------------
# Observabilitate
# -----------------------------------------------------------------------------


class RezumatZilnicEtapaResponse(BaseModel):
    zi: str
    etapa: str
    reusite: int
    esuate: int
    sarite: int
    latenta_medie_ms: float | None = None
    latenta_p95_ms: float | None = None
    tokeni_intrare: int
    tokeni_iesire: int


class RataAcordResponse(BaseModel):
    """Recomandarea etapei de brief vs. decizia finala luata de om."""

    total_comparabile: int
    de_acord: int
    rata: float | None = None


class EtapaSpecResponse(BaseModel):
    """Documentatie executabila — acelasi obiect din app/credit/ai/contracte.py,
    ca sectiunea sa nu se poata desincroniza de comportament (tiparul agents/specs.py)."""

    id: str
    scop: str
    responsabilitati: list[str]
    interzis: list[str]
    are_nevoie_de_model: bool
    versiune_prompt: str | None = None
    # Promptul trimis efectiv modelului, citit din app/credit/ai/prompturi.py.
    # Ruta e sub `cere_administrator`, deci nu iese din zona de administrare.
    prompt_sistem: str | None = None


class ObservabilitateAiResponse(BaseModel):
    rezumat_zilnic: list[RezumatZilnicEtapaResponse]
    rata_acord: RataAcordResponse
    # Ultimele 30 de zile — credit_ai_rulari (etapele 1-3) + ai_usage_records
    # cu feature='credit_pipeline' (etapa 4, care ruleaza sincron in evalueaza()).
    cost_estimat_usd_30_zile: float
    etape: list[EtapaSpecResponse]
