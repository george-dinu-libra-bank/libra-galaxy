"""Revizuirea manuala a verificarilor de identitate.

Fiecare ruta de aici cere rol de admin. Verificarea se face pe server, la
fiecare cerere: butonul ascuns in interfata nu e o bariera, oricine poate chema
ruta direct.

Datele se citesc cu service-role, fiindca trec peste toate conturile si fiindca
URL-urile semnate se cer tot de acolo. Service-role ocoleste RLS, deci
autorizarea nu mai vine din baza de date — vine din `cere_administrator` de mai
jos, si trebuie sa fie acolo pe fiecare ruta, fara exceptie.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import UserContext, cere_administrator
from app.infrastructure.errors import ErrorAplicatie
from app.repositories import identity_repository as depozit
from app.schemas.identity import (
    CazVerificare,
    CazVerificareDetaliu,
    ContNeinceput,
    DecizieRequest,
    DecizieResponse,
    ForteazaVerificareRequest,
    ForteazaVerificareResponse,
)
from app.services import admin_identity_service as serviciu

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/identity/admin", tags=["identity-admin"])


def _urma(
    administrator: UserContext,
    actiune: str,
    id_utilizator: str | None = None,
    detalii: str | None = None,
) -> None:
    """Scrie urma fara sa poata darama cererea.

    O revizuire care esueaza fiindca n-a putut scrie o linie de audit ar fi mai
    rea decat una facuta cu urma lipsa. Lipsa se vede in loguri.
    """
    try:
        depozit.scrie_acces(str(administrator.user_id), actiune, id_utilizator, detalii)
    except Exception:
        logger.exception(
            "nu am putut scrie urma administrator=%s actiune=%s",
            administrator.user_id,
            actiune,
        )


def _http(exc: ErrorAplicatie) -> HTTPException:
    return HTTPException(status_code=exc.status_http, detail={"cod": exc.cod, "mesaj": exc.mesaj})


@router.get("/pending", response_model=list[CazVerificare])
def pending(
    limita: int = Query(default=100, ge=1, le=500),
    administrator: UserContext = Depends(cere_administrator),
) -> list[CazVerificare]:
    """Cazurile care asteapta o hotarare omeneasca."""
    cazuri = serviciu.cazuri_de_revizuit(limita)
    _urma(administrator, "lista_verificari", detalii=f"cazuri={len(cazuri)}")
    return cazuri


@router.get("/case/{id_verificare}", response_model=CazVerificareDetaliu)
def caz(
    id_verificare: str,
    administrator: UserContext = Depends(cere_administrator),
) -> CazVerificareDetaliu:
    """Un caz, cu link-uri temporare catre cele doua poze."""
    try:
        detaliu = serviciu.caz_cu_poze(id_verificare)
    except ErrorAplicatie as exc:
        raise _http(exc) from exc

    _urma(administrator, "vede_verificare", detaliu.id_user, f"caz={id_verificare}")
    return detaliu


@router.post("/review", response_model=DecizieResponse)
def review(
    cerere: DecizieRequest,
    administrator: UserContext = Depends(cere_administrator),
) -> DecizieResponse:
    """Aproba sau respinge un caz. Statusul ajunge si in profil, prin trigger."""
    try:
        rezultat = serviciu.decide(
            cerere.verification_id,
            cerere.decizie,
            str(administrator.user_id),
            cerere.note,
        )
    except ErrorAplicatie as exc:
        raise _http(exc) from exc

    _urma(
        administrator,
        "decide_verificare",
        detalii=f"caz={cerere.verification_id} decizie={cerere.decizie}",
    )
    return rezultat


@router.get("/neincepute", response_model=list[ContNeinceput])
def neincepute(
    limita: int = Query(default=100, ge=1, le=500),
    administrator: UserContext = Depends(cere_administrator),
) -> list[ContNeinceput]:
    """Conturi fara nicio dovada trimisa — nimic de revizuit, doar de deblocat manual."""
    conturi = serviciu.conturi_neincepute(limita)
    _urma(administrator, "lista_neincepute", detalii=f"conturi={len(conturi)}")
    return conturi


@router.post("/forteaza-verificare", response_model=ForteazaVerificareResponse)
def forteaza(
    cerere: ForteazaVerificareRequest,
    administrator: UserContext = Depends(cere_administrator),
) -> ForteazaVerificareResponse:
    """Marcheaza manual contul ca verificat, fara OCR/selfie — pentru conturi
    ramase blocate inainte sa apuce sa trimita dovezi."""
    try:
        rezultat = serviciu.forteaza_verificare(cerere.user_id)
    except ErrorAplicatie as exc:
        raise _http(exc) from exc

    _urma(administrator, "forteaza_verificare", cerere.user_id, detalii=cerere.note)
    return rezultat
