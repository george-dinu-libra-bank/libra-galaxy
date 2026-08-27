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
    # O suma pe (categorie, valuta) — niciodata convertita aici: backend-ul n-are
    # acces la cursuri valutare (acelea traiesc doar in Next.js/Supabase, vezi
    # frontend/src/lib/data/curs-valutar.ts). Conversia si insumarea pe categorie
    # se fac client-side (lib/categorii.ts::totalizeazaPeCategorie), la fel ca
    # totalul din conturi (lib/valute.ts::totalSoldIn).
    valuta: str
    total: float


class CheltuieliPeCategorieResponse(BaseModel):
    luna: str  # YYYY-MM
    categorii: list[CategorieCheltuiala]


class TranzactieCategorizata(BaseModel):
    data: str
    suma: float
    valuta: str
    descriere: str | None
    directie: str
    categorie: str


class SeteazaCategorieRequest(BaseModel):
    id_tranzactie: str
    categorie: str


class SeteazaCategorieResponse(BaseModel):
    id_tranzactie: str
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
