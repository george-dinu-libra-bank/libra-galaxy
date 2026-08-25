from typing import Literal

from pydantic import BaseModel, Field


class ContSemnalatResponse(BaseModel):
    """Un rand din lista administratorului."""

    id_utilizator: str
    nume: str
    email: str
    numar_semnalari: int = Field(ge=0)
    scor_maxim: float
    # Cat de urgent merita contul o privire: tine cont si de cate
    # semnalari sunt, si de cati bani, nu doar de cea mai grava plata.
    gravitate: int
    suma_totala: float
    tipuri: list[str]


class RaportResponse(BaseModel):
    """Raportul in JSON, pentru interfata. Aceleasi date ca in PDF si CSV."""

    id_utilizator: str
    nume: str
    email: str
    iban: str
    zile: int
    generat_la: str
    total_tranzactii: int
    numar_semnalari: int
    suma_semnalata: float
    scor_maxim: float
    pe_tip: dict[str, int]
    sinteza: str | None = None
    constatari: list[dict]


class StareModelResponse(BaseModel):
    """Daca al doilea strat de detectie ruleaza.

    Se afiseaza in panou: cine ia decizii pe baza listei de conturi semnalate
    are dreptul sa stie daca modelul a participat sau lista vine doar din
    reguli statistice.
    """

    activ: bool
    antrenat_la: str | None = None
    marime_kb: int | None = None
    explicatie: str


# -----------------------------------------------------------------------------
# Analiza administratorului asupra unui cont
# -----------------------------------------------------------------------------


class AnalizaRequest(BaseModel):
    # acceptat = am verificat, semnalele nu se confirma
    # frauda   = suspiciunea se confirma; se CONSEMNEAZA, nu blocheaza singura
    # deblocat = blocarea se ridica
    decizie: Literal["acceptat", "frauda", "deblocat"]
    # Blocarea cardurilor se cere anume, nu decurge din verdict: un
    # administrator poate consemna o frauda fara sa ia inca vreo masura.
    aplica_blocarea: bool = False
    observatie: str | None = Field(default=None, max_length=2000)
    # Ce se vedea pe ecran cand s-a decis; se ingheata in istoric.
    gravitate: int | None = Field(default=None, ge=0, le=100)
    numar_semnalari: int | None = Field(default=None, ge=0)
    zile: int | None = Field(default=None, ge=1, le=365)


class AnalizaResponse(BaseModel):
    decizie: str
    observatie: str | None = None
    conturi_atinse: int
    notificare_trimisa: bool
    creat_la: str


class IstoricAnalizaResponse(BaseModel):
    id: str
    decizie: str
    observatie: str | None = None
    gravitate: int | None = None
    numar_semnalari: int | None = None
    conturi_blocate: int
    creat_la: str


class StareContResponse(BaseModel):
    """Istoricul deciziilor plus starea reala a cardurilor.

    Starea nu se deduce din ultima decizie: un administrator poate bloca sau
    debloca oricand, iar istoricul unei singure analize nu spune unde s-a ajuns.
    """

    conturi_total: int
    conturi_blocate: int
    analize: list[IstoricAnalizaResponse]


class StareConturiResponse(BaseModel):
    """Cate conturi are un om si cate ii sunt blocate administrativ."""

    id_utilizator: str
    total: int
    blocate: int
