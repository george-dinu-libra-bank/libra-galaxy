from pydantic import BaseModel


class SoldSumar(BaseModel):
    """Soldul sta pe conturile bancare. Cardurile sunt instrumente de plata,
    nu pungi separate de bani — de aceea nu se aduna la total."""

    total_disponibil: float
    valuta: str = "RON"
    numar_conturi: int
    numar_carduri: int
    carduri_blocate: int


class LunaCashflow(BaseModel):
    luna: str  # YYYY-MM
    incasari: float
    cheltuieli: float
    net: float


class CashflowResponse(BaseModel):
    valuta: str = "RON"
    luni: list[LunaCashflow]
    media_lunara_cheltuieli: float


class CategorieCheltuiala(BaseModel):
    categorie: str
    total: float


class CheltuieliPeCategorieResponse(BaseModel):
    luna: str  # YYYY-MM
    valuta: str = "RON"
    categorii: list[CategorieCheltuiala]


class TranzactieCategorizata(BaseModel):
    data: str
    suma: float
    valuta: str
    descriere: str | None
    directie: str
    categorie: str


class AlertaResponse(BaseModel):
    id_tranzactie: str
    data: str
    suma: float
    valuta: str
    comerciant: str
    tip: str
    explicatie: str
    scor: float
