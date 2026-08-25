"""Contractele HTTP pentru creditare.

Sumele circula ca `Decimal`, nu `float`: pydantic le serializeaza ca string in
JSON, iar frontendul le parseaza cu `Number()`. Un float aici ar reintroduce
exact erorile de virgula mobila pe care amortizare.py le evita lucrand in bani.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.credit_ai import DosarAiResponse, SemnaleRezumatResponse


class RataResponse(BaseModel):
    numar: int
    scadenta: str
    principal: Decimal
    dobanda: Decimal
    total: Decimal
    sold_dupa: Decimal


class SimulareRequest(BaseModel):
    suma: Decimal = Field(gt=0)
    luni: int = Field(ge=1, le=120)


class SimulareResponse(BaseModel):
    suma: Decimal
    luni: int
    dobanda_anuala: Decimal
    rata_lunara: Decimal
    dae: Decimal
    total_platit: Decimal
    cost_total: Decimal
    grafic: list[RataResponse]


class ProdusResponse(BaseModel):
    slug: str
    nume: str
    dobanda_anuala: Decimal
    suma_min: Decimal
    suma_max: Decimal
    luni_min: int
    luni_max: int
    venit_net_minim: Decimal


class CerereRequest(BaseModel):
    suma: Decimal = Field(gt=0)
    luni: int = Field(ge=1, le=120)
    venit_declarat: Decimal = Field(gt=0)
    scop: str | None = Field(default=None, max_length=200)
    angajator: str | None = Field(default=None, max_length=120)
    vechime_angajator_luni: int = Field(default=0, ge=0, le=720)
    obligatii_declarate: Decimal = Field(default=Decimal(0), ge=0)
    # Fara bifa nu se depune cererea: declaratia de venit e pe proprie raspundere,
    # iar consimtamantul pentru verificari trebuie sa fie explicit.
    consimtamant: bool


class CerereResponse(BaseModel):
    id: str
    status: str
    suma_ceruta: Decimal
    luni: int
    creat_la: str
    scor: int | None = None
    dti: Decimal | None = None
    rata_lunara: Decimal | None = None
    dae: Decimal | None = None
    explicatie: str | None = None
    oferta_expira_la: datetime | None = None
    # Mesaje de la banca pe care clientul nu le-a deschis inca — sursa bulinei.
    mesaje_necitite: int = 0


class MotivResponse(BaseModel):
    cod: str
    text: str


class FactorResponse(BaseModel):
    cod: str
    puncte: int
    maxim: int
    explicatie: str


class DecizieResponse(BaseModel):
    decizie: str
    scor: int | None
    dti: Decimal | None
    motive: list[MotivResponse]
    factori: list[FactorResponse]
    explicatie: str
    rata_lunara: Decimal | None = None
    dae: Decimal | None = None
    oferta_expira_la: datetime | None = None
    cere_document: bool = False


class AcceptaRequest(BaseModel):
    id_cont: str


class AcordareResponse(BaseModel):
    id_credit: str
    id_tranzactie: str
    principal: Decimal
    rata_lunara: Decimal
    luni: int
    sold_cont_nou: Decimal
    prima_scadenta: str


class CreditResponse(BaseModel):
    id: str
    principal: Decimal
    dobanda_anuala: Decimal
    luni: int
    rata_lunara: Decimal
    dae: Decimal | None
    sold_ramas: Decimal
    data_acordarii: str
    status: str
    inchis_la: datetime | None = None


class RataDetaliuResponse(BaseModel):
    numar_rata: int
    scadenta: str
    principal_rata: Decimal
    dobanda_rata: Decimal
    rata_totala: Decimal
    sold_dupa: Decimal
    status: str
    platita_la: datetime | None = None


class DetaliuCreditResponse(BaseModel):
    credit: CreditResponse
    rate: list[RataDetaliuResponse]
    urmatoarea_rata: RataDetaliuResponse | None
    rate_platite: int


class RambursareCalculResponse(BaseModel):
    sold: Decimal
    dobanda_acumulata: Decimal
    total_de_plata: Decimal
    economie_dobanda: Decimal
    zile_de_la_ultima_scadenta: int


class RambursareRequest(BaseModel):
    """`suma` lipsa inseamna stingere integrala."""

    suma: Decimal | None = Field(default=None, gt=0)


class RambursareResponse(BaseModel):
    id_tranzactie: str
    principal_platit: Decimal
    dobanda_platita: Decimal
    total_platit: Decimal
    sold_ramas: Decimal
    status: str
    sold_cont: Decimal


ActiuneAnalist = Literal[
    "aproba", "respinge", "cere_documente", "notifica", "retrage_oferta"
]

# Actiunile al caror singur efect vizibil pentru client e textul scris de
# analist. Fara mesaj n-ar afla nici ce lipseste, nici ce nu e in regula.
# `retrage_oferta` e aici din alt motiv: acolo mesajul nu explica ce sa faca, ci
# de ce i-a disparut ceva ce avea deja.
ACTIUNI_CU_MESAJ_OBLIGATORIU = ("cere_documente", "notifica", "retrage_oferta")


class DecizieManualaRequest(BaseModel):
    """Ce face analistul cu un dosar aflat in lucru.

    Cinci iesiri, nu doua: doua inchid discutia (`aproba`/`respinge`), doua o tin
    deschisa — `cere_documente` muta mingea la client, `notifica` doar il
    anunta, fara sa schimbe starea dosarului. A cincea, `retrage_oferta`, e
    singura care lucreaza peste un dosar deja ofertat si il aduce inapoi in
    analiza.
    """

    actiune: ActiuneAnalist
    nota: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _mesajul_e_obligatoriu_unde_trebuie(self) -> "DecizieManualaRequest":
        if self.actiune in ACTIUNI_CU_MESAJ_OBLIGATORIU and not (self.nota or "").strip():
            raise ValueError("Scrie un mesaj pentru client.")
        return self


class CerereAdminResponse(CerereResponse):
    """Cererea, plus cine a depus-o.

    CNP-ul nu apare deloc: pentru a decide asupra unui dosar e de ajuns numele,
    scorul si cifrele. Ce nu se trimite nu se poate scurge.
    """

    nume: str
    venit_folosit: Decimal | None = None
    obligatii_folosite: Decimal | None = None
    # Factorii scorecard-ului, sau motivele de respingere pe criterii hard —
    # coloana `motive` tine si una si alta (vezi _finalizeaza). Un scor fara ele
    # e un numar pe care analistul nu are cum sa il judece.
    motive: list[dict] = Field(default_factory=list)
    # Numarul de semnale AI din ultima rulare (pipeline consultativ, app/credit/ai/).
    # None cand pipeline-ul n-a rulat inca pentru cererea asta.
    semnale: SemnaleRezumatResponse | None = None


# -----------------------------------------------------------------------------
# Documente (adeverinta de venit)
# -----------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    """Un document al cererii.

    `extras` si `venit_confirmat` stau separat dinadins: primul e ce a citit
    OCR-ul, al doilea e ce a hotarat analistul. Cand difera, se vede.
    """

    id: str
    tip: str
    status: str
    content_type: str | None = None
    marime_octeti: int | None = None
    extras: dict = Field(default_factory=dict)
    venit_confirmat: Decimal | None = None
    confirmat_la: datetime | None = None
    sters_la: datetime | None = None
    creat_la: str
    # Link semnat, cu durata scurta. Lipseste cand fisierul a fost sters dupa
    # expirarea retentiei — randul ramane, documentul nu.
    url: str | None = None


class ConfirmaDocumentRequest(BaseModel):
    """Cifra pe care analistul o valideaza dupa ce s-a uitat la document."""

    venit_confirmat: Decimal = Field(gt=0)


class VerificareResponse(BaseModel):
    sursa: str
    venit_constatat: Decimal | None = None
    obligatii_constatate: Decimal | None = None
    incredere: Decimal | None = None
    detalii: dict = Field(default_factory=dict)
    creat_la: str


class MesajResponse(BaseModel):
    """Un mesaj din firul unei cereri.

    `id_document` e completat cand mesajul insoteste un fisier incarcat —
    interfata il foloseste ca sa lege bula de document.
    """

    id: str
    autor: str
    text: str
    id_document: str | None = None
    creat_la: datetime
    citit_de_client_la: datetime | None = None


class MesajRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class DosarResponse(BaseModel):
    """Tot ce are nevoie un analist ca sa decida, intr-un singur raspuns."""

    cerere: CerereAdminResponse
    verificari: list[VerificareResponse]
    documente: list[DocumentResponse]
    mesaje: list[MesajResponse] = Field(default_factory=list)
    # None cand pipeline-ul AI n-a rulat inca (Foundry cazut, sau catch-up-ul
    # lazy nu s-a declansat inca) — strict consultativ, niciodata blocant.
    ai: DosarAiResponse | None = None


class CreditAdminResponse(CreditResponse):
    nume: str
