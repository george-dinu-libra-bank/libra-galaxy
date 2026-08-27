from typing import Literal

import anyio
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.core.errors import PermissionDeniedError, ValidationError
from app.core.security import Principal, get_principal_or_internal
from app.infrastructure.rate_limit import limiteaza
from app.schemas.identity import (
    CalitatePozaResponse,
    ExtrageCnpResponse,
    LoginFataResponse,
    ProblemaPoza,
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
async def extract_cnp(request: Request, buletin: UploadFile) -> ExtrageCnpResponse:
    """
    Fara autentificare — se apeleaza inainte de signUp(), cand nu exista inca
    un cont. Imaginea nu se persista: se citeste, se proceseaza prin OCR si se
    arunca la finalul cererii.

    Limita de rata pe IP, ca la /check-photo, dar din alt motiv: citirea trece
    prin Azure Document Intelligence, deci **fiecare apel costa bani**. O ruta
    neautentificata si nelimitata care cheama un API platit e o gaura in
    portofel, nu doar o resursa de calcul irosita. Cat OCR-ul era local si
    gratis, lipsa limitei nu se vedea.

    Pragul e mai strans decat la /check-photo (60): acolo omul chiar reia poza
    de multe ori pana iese bine, aici o trimite o data ce a iesit.
    """
    ip = request.client.host if request.client else "necunoscut"
    limiteaza(f"extract-cnp:ip:{ip}", max_incercari=20, fereastra_secunde=300)

    date = await _citeste_imagine(buletin)
    cnp, incredere = await identity_service.extrage_cnp_din_buletin(date, buletin.content_type)

    return ExtrageCnpResponse(cnp=cnp, confidence=incredere, raw_text_found=cnp is not None)


@router.post("/check-photo", response_model=CalitatePozaResponse)
async def check_photo(
    request: Request,
    imagine: UploadFile = File(...),
    tip: Literal["selfie", "buletin"] = Form("selfie"),
) -> CalitatePozaResponse:
    """
    Spune ce e in neregula cu poza inainte sa fie trimisa mai departe: prea
    intunecata, prea luminoasa, fara nicio fata, neclara.

    Fara autentificare, ca /extract-cnp — se apeleaza in timpul inregistrarii,
    inainte de signUp(), cand nu exista inca o sesiune. Poza nu se persista.

    Rate limit generos pe IP: userul chiar reia poza de cateva ori la rand,
    dar ruta nu trebuie sa devina un API gratuit de detectie faciala.
    """
    ip = request.client.host if request.client else "necunoscut"
    limiteaza(f"check-photo:ip:{ip}", max_incercari=60, fereastra_secunde=300)

    date = await _citeste_imagine(imagine)

    # Analiza e CPU-bound (yunet + numpy) si ar bloca event loop-ul cateva
    # sute de milisecunde pentru toate celelalte cereri.
    raport = await anyio.to_thread.run_sync(identity_service.evalueaza_calitate_poza, date, tip)

    return CalitatePozaResponse(
        acceptabila=raport.acceptabila,
        probleme=[
            ProblemaPoza(cod=problema.cod, mesaj=problema.mesaj, blocanta=problema.blocanta)
            for problema in raport.probleme
        ],
    )


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
