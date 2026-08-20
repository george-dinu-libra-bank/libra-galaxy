"""GET /health — nume de deployment si flag configurat/neconfigurat, niciodata chei (docs/SECURITY.md #4)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.envelope import new_request_id, success

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    settings = get_settings()
    request_id = request.headers.get("X-Request-ID") or new_request_id()

    return success(
        {
            "environment": settings.environment,
            "foundry_configured": settings.foundry_configured,
            "foundry_chat_deployment": settings.foundry_chat_deployment,
            "foundry_embedding_deployment": settings.foundry_embedding_deployment,
            "speech_configured": settings.speech_configured,
            "supabase_configured": settings.supabase_configured,
            "agents_configured": settings.agenti_activi,
        },
        request_id=request_id,
    )
