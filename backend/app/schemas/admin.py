from pydantic import BaseModel, Field


class ContSemnalatResponse(BaseModel):
    """Un rand din lista administratorului."""

    id_utilizator: str
    nume: str
    email: str
    numar_semnalari: int = Field(ge=0)
    scor_maxim: float
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
