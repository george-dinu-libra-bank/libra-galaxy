"""Sesizarile clientului catre banca, si coada administratorului.

Doua audiente pe acelasi obiect: clientul isi trimite si isi vede sesizarile,
administratorul le vede pe toate si raspunde. Separate prin dependinte, nu prin
verificari scrise de mana in fiecare functie.
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from supabase import Client

from app.api.dependencies import (
    UserContext,
    cere_administrator,
    get_admin_supabase,
    get_current_user,
)
from app.repositories.admin_repository import AnalizaRepository
from app.repositories.suport_repository import SuportRepository
from app.services.suport_service import SuportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/suport", tags=["suport"])


def _serviciu(client: Client) -> SuportService:
    return SuportService(SuportRepository(client), AnalizaRepository(client))


class TrimiteSesizareRequest(BaseModel):
    subiect: str = Field(min_length=3, max_length=200)
    rezumat: str = Field(min_length=10, max_length=4000)
    context: dict = Field(default_factory=dict)


class SesizareResponse(BaseModel):
    id: str
    # Fals cand exista deja o sesizare deschisa: nu s-a creat una noua, dar
    # clientul trebuie sa afle ca cererea lui e deja la cineva.
    creata_acum: bool


class RandSesizare(BaseModel):
    id: str
    id_utilizator: str
    subiect: str
    rezumat: str
    status: str
    raspuns: str | None = None
    creat_la: str


class RaspundeRequest(BaseModel):
    raspuns: str = Field(min_length=1, max_length=4000)
    status: str = "rezolvata"


def _rand(r: dict) -> RandSesizare:
    """Un rand din baza, in forma trimisa clientului si administratorului."""
    return RandSesizare(
        id=str(r["id"]),
        id_utilizator=str(r["id_utilizator"]),
        subiect=r["subiect"],
        rezumat=r["rezumat"],
        status=r["status"],
        raspuns=r.get("raspuns"),
        creat_la=str(r["creat_la"]),
    )


@router.post("", response_model=SesizareResponse)
async def trimite(
    cerere: TrimiteSesizareRequest,
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_admin_supabase),
) -> SesizareResponse:
    """Trimite sesizarea, dupa ce clientul a confirmat continutul in aplicatie."""
    rezultat = await _serviciu(client).trimite(
        str(user.user_id), cerere.subiect, cerere.rezumat, cerere.context
    )
    return SesizareResponse(id=rezultat.id, creata_acum=rezultat.creata_acum)


@router.get("/ale-mele", response_model=list[RandSesizare])
async def ale_mele(
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_admin_supabase),
) -> list[RandSesizare]:
    """Sesizarile proprii, cu raspunsurile primite."""
    randuri = await SuportRepository(client).ale_utilizatorului(str(user.user_id))
    return [_rand(r) for r in randuri]


@router.get("/coada", response_model=list[RandSesizare])
async def coada(
    doar_deschise: bool = Query(default=True),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> list[RandSesizare]:
    """Sesizarile de rezolvat, cea mai veche prima."""
    randuri = await _serviciu(client).coada(doar_deschise)
    return [_rand(r) for r in randuri]


@router.post("/{id_cerere}/raspuns", response_model=RandSesizare)
async def raspunde(
    id_cerere: str,
    cerere: RaspundeRequest,
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> RandSesizare:
    """Raspunde clientului. Raspunsul ii ajunge si ca notificare in aplicatie."""
    r = await _serviciu(client).raspunde(
        id_cerere, cerere.raspuns, str(administrator.user_id), cerere.status
    )
    return RandSesizare(
        id=str(r["id"]),
        id_utilizator=str(r["id_utilizator"]),
        subiect=r["subiect"],
        rezumat=r["rezumat"],
        status=r["status"],
        raspuns=r.get("raspuns"),
        creat_la=str(r["creat_la"]),
    )
