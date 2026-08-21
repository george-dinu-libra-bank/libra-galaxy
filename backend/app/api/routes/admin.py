"""Zona administratorului: conturile semnalate si rapoartele lor.

Tot ce e aici cere rol de administrator in baza de date. Verificarea din
dependinta e prima bariera; a doua, cea care conteaza, sunt politicile RLS din
0004_rol_administrator.sql — fara ele, cererile n-ar intoarce nimic oricum.

Fiecare citire lasa o urma in public.acces_administrator: cine s-a uitat la
datele cui si cand.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from supabase import Client
from uuid import UUID

from app.api.dependencies import UserContext, cere_administrator, get_user_supabase
from app.infrastructure.config import Settings, get_settings
from app.ml.neregularitati import DetectorNeregularitati
from app.rapoarte import csv_raport, pdf_raport
from app.repositories.admin_repository import AdminRepository
from app.schemas.admin import ContSemnalatResponse, RaportResponse
from app.services.raport_service import Raport, RaportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _serviciu(client: Client, settings: Settings) -> tuple[RaportService, AdminRepository]:
    depozit = AdminRepository(client)
    serviciu = RaportService(
        depozit,
        DetectorNeregularitati.cu_model_de_pe_disc(),
        settings.analiza_limita_randuri,
    )
    return serviciu, depozit


async def _urma(
    depozit: AdminRepository,
    administrator: UserContext,
    actiune: str,
    id_utilizator: UUID | None = None,
    detalii: str | None = None,
) -> None:
    """Scrie urma fara sa poata darama cererea.

    Un raport care esueaza fiindca n-a putut scrie o linie de audit ar fi mai
    rau decat unul livrat cu urma lipsa. Lipsa se vede in loguri.
    """
    try:
        await depozit.scrie_acces(administrator.user_id, actiune, id_utilizator, detalii)
    except Exception:
        logger.exception(
            "nu am putut scrie urma de acces administrator=%s actiune=%s",
            administrator.user_id,
            actiune,
        )


@router.get("/conturi-semnalate", response_model=list[ContSemnalatResponse])
async def conturi_semnalate(
    zile: int = Query(default=30, ge=1, le=365),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> list[ContSemnalatResponse]:
    """Conturile cu plati atipice, cel mai greu caz primul."""
    serviciu, depozit = _serviciu(client, settings)
    rezumate = await serviciu.conturi_semnalate(zile)
    await _urma(depozit, administrator, "lista_alerte", detalii=f"zile={zile}")
    return [ContSemnalatResponse(**asdict(r)) for r in rezumate]


async def _construieste_raport(
    serviciu: RaportService, user_id: UUID, zile: int, cu_sinteza: bool
) -> Raport:
    raport = await serviciu.raport(user_id, zile)
    if raport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contul nu a fost gasit."
        )

    if cu_sinteza and raport.constatari:
        # Sinteza e in plus, nu in locul faptelor: daca modelul lipseste sau
        # cade, raportul pleaca la fel, doar fara paragraful de sus.
        try:
            from app.infrastructure.llm import get_client_model
            from app.services.sinteza import scrie_sinteza

            if get_settings().agenti_activi:
                raport.sinteza = await scrie_sinteza(raport, get_client_model())
        except Exception:
            logger.exception("sinteza a esuat; trimit raportul fara ea")

    return raport


@router.get("/raport/{id_utilizator}", response_model=RaportResponse)
async def raport_json(
    id_utilizator: UUID,
    zile: int = Query(default=180, ge=1, le=365),
    sinteza: bool = Query(default=False, description="adauga paragraful scris de model"),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> RaportResponse:
    serviciu, depozit = _serviciu(client, settings)
    raport = await _construieste_raport(serviciu, id_utilizator, zile, sinteza)
    await _urma(depozit, administrator, "lista_alerte", id_utilizator, f"zile={zile}")

    return RaportResponse(
        id_utilizator=raport.id_utilizator,
        nume=raport.nume,
        email=raport.email,
        iban=raport.iban,
        zile=raport.zile,
        generat_la=raport.generat_la.isoformat(),
        total_tranzactii=raport.total_tranzactii,
        numar_semnalari=len(raport.constatari),
        suma_semnalata=raport.suma_semnalata,
        scor_maxim=raport.scor_maxim,
        pe_tip=raport.pe_tip,
        sinteza=raport.sinteza,
        constatari=[asdict(c) for c in raport.constatari],
    )


@router.get("/raport/{id_utilizator}/pdf")
async def raport_pdf(
    id_utilizator: UUID,
    zile: int = Query(default=180, ge=1, le=365),
    sinteza: bool = Query(default=True),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> Response:
    serviciu, depozit = _serviciu(client, settings)
    raport = await _construieste_raport(serviciu, id_utilizator, zile, sinteza)
    await _urma(depozit, administrator, "raport_pdf", id_utilizator, f"zile={zile}")

    return Response(
        content=pdf_raport.randeaza(raport),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_raport.nume_fisier(raport)}"'
        },
    )


@router.get("/raport/{id_utilizator}/csv")
async def raport_csv(
    id_utilizator: UUID,
    zile: int = Query(default=180, ge=1, le=365),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> Response:
    serviciu, depozit = _serviciu(client, settings)
    raport = await _construieste_raport(serviciu, id_utilizator, zile, cu_sinteza=False)
    await _urma(depozit, administrator, "raport_csv", id_utilizator, f"zile={zile}")

    return Response(
        content=csv_raport.randeaza(raport),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{csv_raport.nume_fisier(raport)}"'
        },
    )
