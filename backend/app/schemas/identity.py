from typing import Literal

from pydantic import BaseModel, Field


class ExtrageCnpResponse(BaseModel):
    cnp: str | None
    confidence: float
    raw_text_found: bool


class VerificaIdentitateRequest(BaseModel):
    user_id: str
    buletin_path: str = Field(..., description="Cale in bucket-ul 'buletine'")
    selfie_path: str = Field(..., description="Cale in bucket-ul 'selfie-uri'")
    extracted_cnp: str | None = None


class VerificaIdentitateResponse(BaseModel):
    verified: bool
    score: float | None
    threshold: float
    status: str


class LoginFataResponse(BaseModel):
    """
    Raspuns intentionat minimal: nu spunem daca emailul exista sau daca
    userul are/nu are o poza verificata — doar 'matched'. Orice detaliu in
    plus ar ajuta pe cineva sa ghiceasca ce conturi exista sau sunt
    verificate biometric.
    """

    matched: bool


# -----------------------------------------------------------------------------
# Panoul de administrator
# -----------------------------------------------------------------------------


class CazVerificare(BaseModel):
    """Un caz de verificare, asa cum il vede administratorul.

    Despre `distanta_fete`: DeepFace intoarce o DISTANTA, nu o similaritate.
    Mai mic inseamna mai asemanator, iar potrivirea trece cand distanta <= prag
    (vezi infrastructure/face_match.py). Coloana din baza de date se numeste
    `similarity_score` din motive istorice, dar contine tot o distanta. Numele
    de aici e cel corect, ca sa nu ajunga cineva sa respinga un cont bun
    crezand ca un numar mic inseamna potrivire slaba.
    """

    id: str
    id_user: str
    nume: str
    email: str
    cnp_declarat: str | None = None
    cnp_extras: str | None = None
    cnp_se_potriveste: bool | None = None
    distanta_fete: float | None = None
    prag: float | None = None
    sub_prag: bool | None = Field(
        default=None,
        description="Distanta <= prag, adica fetele se potrivesc. None cand nu s-a detectat o fata.",
    )
    status: str
    creat_la: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None


class CazVerificareDetaliu(CazVerificare):
    """Cazul plus link-uri temporare catre poze (URL semnat, nu public)."""

    url_buletin: str | None = None
    url_selfie: str | None = None
    secunde_valabilitate: int


class DecizieRequest(BaseModel):
    verification_id: str
    decizie: Literal["verified", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class DecizieResponse(BaseModel):
    id: str
    status: str
    reviewed_at: str | None = None


class ContNeinceput(BaseModel):
    """Un cont ramas pe verification_status='pending' — nicio dovada trimisa."""

    id: str
    nume: str
    email: str
    creat_la: str


class ForteazaVerificareRequest(BaseModel):
    user_id: str
    note: str | None = Field(default=None, max_length=2000)


class ForteazaVerificareResponse(BaseModel):
    id: str
    verification_status: str
