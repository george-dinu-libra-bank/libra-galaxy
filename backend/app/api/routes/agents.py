from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.agents.spending_agent import SpendingAgent
from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.anthropic import get_anthropic_client
from app.infrastructure.config import Settings, get_settings
from app.repositories.card_repository import CardRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.agents import ChatRequest, ChatResponse
from app.services.spending_service import SpendingService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    cerere: ChatRequest,
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    if not settings.agenti_activi:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Asistentul nu este configurat pe acest mediu.",
        )

    service = SpendingService(TransactionRepository(client), CardRepository(client))
    agent = SpendingAgent(get_anthropic_client(), settings, service, user.user_id)

    return await agent.raspunde(cerere)
