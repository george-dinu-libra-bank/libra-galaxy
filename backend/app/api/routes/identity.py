from fastapi import APIRouter, Depends, UploadFile

from app.core.errors import PermissionDeniedError, ValidationError
from app.core.security import Principal, get_principal_or_internal
from app.schemas.identity import (
    ExtrageCnpResponse,
    VerificaIdentitateRequest,
    VerificaIdentitateResponse,
)
from app.services import identity_service

router = APIRouter(prefix="/api/identity", tags=["identity"])

MAX_OCTETI_IMAGINE = 8 * 1024 * 1024


async def _citeste_imagine(fisier: UploadFile) -> bytes:
    date = await fisier.read()
    if not date:
        raise ValidationError("Fisier gol.")
    if len(date) > MAX_OCTETI_IMAGINE:
        raise ValidationError("Imagine prea mare.")
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
    principal: Principal = Depends(get_principal_or_internal),
) -> VerificaIdentitateResponse:
    if cerere.user_id != principal.user_id:
        raise PermissionDeniedError("user_id nu corespunde contextului autentificat.")

    # IdentityImageDownloadError/IdentityResultWriteError (core/errors.py) trec
    # neprinse pana la handler-ul global din main.py — acelasi plic ca restul API-ului.
    return identity_service.verifica_identitate(cerere)
