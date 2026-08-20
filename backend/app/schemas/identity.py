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


class EroareResponse(BaseModel):
    """Forma standard a oricarei erori intoarse de API — vezi app/main.py si infrastructure/errors.py."""

    cod: str
    mesaj: str
