from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.agents.registru import construieste_orchestrator
from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.llm import get_client_model
from app.infrastructure.config import Settings, get_settings
from app.schemas.agents import ChatRequest, ChatResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    cerere: ChatRequest,
    user: UserContext = Depends(get_current_user),
    client_supabase: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """Punctul unic de intrare. Orchestratorul decide ce agent raspunde."""
    if not settings.agenti_activi:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asistentul nu este configurat pe acest mediu (lipsesc credentialele Azure).",
        )

    orchestrator = construieste_orchestrator(
        get_client_model(), client_supabase, settings, user.user_id
    )
    return await orchestrator.raspunde(cerere)
