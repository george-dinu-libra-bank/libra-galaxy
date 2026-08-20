from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.agents.registru import construieste_analiza
from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.config import Settings, get_settings
from app.schemas.analiza import AlertaResponse

router = APIRouter(prefix="/alerte", tags=["alerte"])


@router.get("", response_model=list[AlertaResponse])
async def alerte(
    zile: int = Query(default=180, ge=1, le=365),
    user: UserContext = Depends(get_current_user),
    client_supabase: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> list[AlertaResponse]:
    """Platile care ies din tiparul utilizatorului.

    Nu trece prin niciun model de limbaj: e detectie statistica plus, daca exista
    artefactul antrenat, modelul. De aceea merge si fara ANTHROPIC_API_KEY.
    """
    analiza = construieste_analiza(client_supabase, settings)
    constatari = await analiza.neregularitati(user.user_id, zile)
    return [AlertaResponse(**asdict(c)) for c in constatari]
