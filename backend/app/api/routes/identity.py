from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.dependencies import AuthContext, get_current_user_or_internal
from app.infrastructure.errors import ErrorAplicatie
from app.infrastructure.rate_limit import limiteaza
from app.services import identity_service
from app.schemas.identity import (
    ExtrageCnpResponse,
    LoginFataResponse,
    VerificaIdentitateRequest,
    VerificaIdentitateResponse,
)

router = APIRouter(prefix="/api/identity", tags=["identity"])

MAX_OCTETI_IMAGINE = 8 * 1024 * 1024


async def _citeste_imagine(fisier: UploadFile) -> bytes:
    date = await fisier.read()
    if not date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fisier gol.")
    if len(date) > MAX_OCTETI_IMAGINE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Imagine prea mare.")
    return date


@router.post("/extract-cnp", response_model=ExtrageCnpResponse)
async def extract_cnp(buletin: UploadFile) -> ExtrageCnpResponse:
    """
    Fara autentificare — se apeleaza inainte de signUp(), cand nu exista inca
    un cont. Imaginea nu se persista: se citeste, se proceseaza prin OCR si se
    arunca la finalul cererii.
    """
    date = await _citeste_imagine(buletin)
    cnp, incredere = identity_service.extrage_cnp_din_buletin(date)

    return ExtrageCnpResponse(cnp=cnp, confidence=incredere, raw_text_found=cnp is not None)


@router.post("/verify", response_model=VerificaIdentitateResponse)
async def verify(
    cerere: VerificaIdentitateRequest,
    context: AuthContext = Depends(get_current_user_or_internal),
) -> VerificaIdentitateResponse:
    if cerere.user_id != context.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"cod": "user_id_neconcordant", "mesaj": "user_id nu corespunde contextului autentificat."},
        )

    try:
        return identity_service.verifica_identitate(cerere)
    except ErrorAplicatie as exc:
        raise HTTPException(status_code=exc.status_http, detail={"cod": exc.cod, "mesaj": exc.mesaj}) from exc


@router.post("/login-match", response_model=LoginFataResponse)
async def login_match(request: Request, email: str = Form(...), imagine: UploadFile = File(...)) -> LoginFataResponse:
    """
    Fara autentificare (userul inca nu are sesiune — asta chiar e pasul de
    login). Protejata doar prin rate limiting pe email+IP, ca sa nu poata
    cineva incerca poze la infinit pe un email cunoscut sau sa scaneze multe
    conturi de pe aceeasi masina. Raspunsul e intentionat minimal (doar
    matched: bool) — vezi LoginFataResponse.
    """
    ip = request.client.host if request.client else "necunoscut"
    limiteaza(f"login-match:email:{email.strip().lower()}", max_incercari=5, fereastra_secunde=300)
    limiteaza(f"login-match:ip:{ip}", max_incercari=20, fereastra_secunde=300)

    date = await _citeste_imagine(imagine)
    matched = identity_service.verifica_login_fata(email, date)

    return LoginFataResponse(matched=matched)
