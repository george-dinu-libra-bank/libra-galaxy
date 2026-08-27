from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ContClientResponse(BaseModel):
    nume: str | None = None
    sold: str
    valuta: str | None = None
    blocat: bool = False


class CerereStergereAdminResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    id_utilizator: UUID
    nume: str | None = None
    email: str | None = None
    motiv: str | None = None
    status: str
    creat_la: datetime
    decis_la: datetime | None = None
    motiv_refuz: str | None = None
    conturi: list[ContClientResponse] = []
    credite_in_derulare: int = 0


class DecizieStergereRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aproba: bool
    motiv: str | None = Field(default=None, max_length=500)


# -----------------------------------------------------------------------------
# Inchiderea unui CONT BANCAR (nu a relatiei cu banca)
# -----------------------------------------------------------------------------


class ContAdminResponse(BaseModel):
    """Un cont, asa cum il vede analistul: si cel care se inchide, si cele care
    pot primi banii. O singura forma pentru amandoua, ca sa arate la fel."""

    id: UUID
    nume: str | None = None
    sold: str
    valuta: str | None = None
    blocat: bool = False
    inchis: bool = False
    este_principal: bool = False


class CardInchisResponse(BaseModel):
    id: UUID
    ultimele4: str
    tip: str | None = None


class CerereInchidereContResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    id_utilizator: UUID
    id_cont: UUID
    id_cont_destinatie: UUID | None = None
    nume: str | None = None
    email: str | None = None
    motiv: str | None = None
    status: str
    creat_la: datetime
    decis_la: datetime | None = None
    motiv_refuz: str | None = None

    cont: ContAdminResponse | None = None
    # Doar conturile deschise, altele decat cel care se inchide. Lista vine gata
    # filtrata din depozit: mai bine lipsesc optiunile imposibile decat sa fie
    # afisate dezactivate.
    destinatii: list[ContAdminResponse] = []
    carduri: list[CardInchisResponse] = []


class DecizieInchidereRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aproba: bool
    # Lipsa inseamna „automat": RPC-ul cade pe propunerea clientului, iar daca
    # nici ea nu exista, pe contul principal.
    id_cont_destinatie: UUID | None = None
    motiv: str | None = Field(default=None, max_length=500)


# -----------------------------------------------------------------------------
# Popriri
#
# Alta operatiune decat blocarea contului, si nu trebuie confundata cu ea:
# blocarea opreste TOT ce pleaca dintr-un cont, poprirea indisponibilizeaza o
# SUMA pe toate conturile clientului. Pot fi si amandoua deodata.
# -----------------------------------------------------------------------------


class PoprireResponse(BaseModel):
    """Un dosar de poprire, asa cum il vede analistul.

    ATENTIE la sumele ca text: acelasi camp vine in DOUA forme, dupa drum.
    PostgREST serializeaza `numeric` ca SIR cand citesti tabela, dar ca NUMAR
    cand il intoarce un RPC. Prima varianta a acestui model declara doar `str`,
    si efectul era exact pe dos decat cel util: lista mergea (era goala), iar
    instituirea unei popriri dadea 500 DUPA ce RPC-ul scrisese deja randul in
    baza — adica omul primea „eroare" si o poprire reala pe cont.

    Normalizarea sta aici, intr-un singur loc, si nu in cele patru rute: e
    singurul punct prin care trec amandoua formele.
    """

    model_config = ConfigDict(extra="ignore")

    id: UUID
    id_utilizator: UUID
    creditor: str
    dosar: str | None = None
    suma_totala: str
    suma_incasata: str
    valuta: str = "RON"
    status: str
    creat_la: datetime
    incheiat_la: datetime | None = None
    observatie: str | None = None

    # Vin din alaturarea facuta in depozit, ca analistul sa nu ceara a doua oara.
    nume: str | None = None
    email: str | None = None
    # Soldul cumulat al clientului, in RON. Fara el, „mai are de platit 5000" nu
    # spune daca poprirea se poate incasa azi sau nu.
    disponibil: str | None = None

    @field_validator("suma_totala", "suma_incasata", "disponibil", mode="before")
    @classmethod
    def _bani_ca_text(cls, valoare: object) -> object:
        """Orice ar veni — sir, float, Decimal — iese „1234.50".

        Trecerea prin `Decimal(str(...))` si nu prin `float` e intentionata: pe
        bani nu se face aritmetica in virgula mobila nicaieri in proiectul asta.
        """
        if valoare is None or isinstance(valoare, str):
            return valoare
        if isinstance(valoare, (int, float, Decimal)):
            return str(Decimal(str(valoare)).quantize(Decimal("0.01")))
        return valoare


class InstituiePoprireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_utilizator: UUID
    creditor: str = Field(min_length=2, max_length=200)
    suma: Decimal = Field(gt=0)
    dosar: str | None = Field(default=None, max_length=100)
    observatie: str | None = Field(default=None, max_length=2000)


class IncaseazaPoprireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Lipsa inseamna „cat se poate acum" — forma folosita in practica, fiindca
    # banii pica in transe.
    suma: Decimal | None = Field(default=None, gt=0)


class RidicaPoprireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motiv: str | None = Field(default=None, max_length=500)


class StorneazaPoprireRequest(BaseModel):
    """Reverse-ul unei incasari: banii virati se intorc la client.

    Nu e acelasi lucru cu ridicarea. Ridicarea opreste poprirea; stornarea aduce
    banii inapoi. O poprire pusa gresit si deja incasata cere amandoua, in
    ordinea asta.
    """

    model_config = ConfigDict(extra="forbid")

    # Lipsa inseamna „tot ce s-a incasat".
    suma: Decimal | None = Field(default=None, gt=0)
    motiv: str | None = Field(default=None, max_length=500)
