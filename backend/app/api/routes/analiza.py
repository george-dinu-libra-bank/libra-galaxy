from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.agents.registru import construieste_analiza
from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.config import Settings, get_settings
from app.schemas.analiza import CashflowResponse, CheltuieliPeCategorieResponse, TranzactieCategorizata

router = APIRouter(prefix="/analiza", tags=["analiza"])


@router.get("/cheltuieli-pe-categorie", response_model=CheltuieliPeCategorieResponse)
async def cheltuieli_pe_categorie(
    user: UserContext = Depends(get_current_user),
    client_supabase: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> CheltuieliPeCategorieResponse:
    """Cheltuielile lunii calendaristice curente, pe categorie — widgetul de
    dashboard. Categoria e determinista (tools/categorii_tranzactii.py),
    niciodata ghicita de un model (CLAUDE.md #25)."""
    analiza = construieste_analiza(client_supabase, settings)
    return await analiza.cheltuieli_pe_categorie_luna_curenta(user.user_id)


@router.get("/cashflow", response_model=CashflowResponse)
async def cashflow(
    luni: int = Query(default=1, ge=1, le=12),
    user: UserContext = Depends(get_current_user),
    client_supabase: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> CashflowResponse:
    analiza = construieste_analiza(client_supabase, settings)
    return await analiza.cashflow_lunar(user.user_id, luni=luni)


@router.get("/tranzactii-categorizate", response_model=list[TranzactieCategorizata])
async def tranzactii_categorizate(
    zile: int = Query(default=31, ge=1, le=365),
    limita: int = Query(default=200, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    client_supabase: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> list[TranzactieCategorizata]:
    """Tranzactii recente, deja categorizate — folosit de pagina de categorie
    (frontend/src/app/(app)/categorii/[categorie]/page.tsx) ca sa filtreze pe
    categorie fara sa reimplementeze categorizeaza() in TypeScript (CLAUDE.md #7)."""
    analiza = construieste_analiza(client_supabase, settings)
    randuri = await analiza.tranzactii_recente(user.user_id, zile=zile, limita=limita)
    return [TranzactieCategorizata(**rand) for rand in randuri]
