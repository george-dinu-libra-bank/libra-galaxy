from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, agents, alerte, assistant, credite, health, identity, profiles
from app.api.routes.admin_identity import router as admin_identity_router
from app.core.config import get_settings
from app.core.envelope import error_response, new_request_id
from app.core.errors import AppError
from app.core.logging import request_id_var, setup_logging

setup_logging()
logger = logging.getLogger("libra.assistant")

settings = get_settings()

app = FastAPI(title="Libra Galaxy — Asistent AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    # Lista explicita, nu "*": cu allow_credentials=True browserele resping
    # wildcard-ul, iar antetele proprii (X-Internal-Api-Key, X-User-Id) trebuie
    # oricum enumerate ca sa treaca de preflight.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key",
                   "X-Internal-Api-Key", "X-User-Id"],
)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, error: AppError):
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    logger.warning("app_error", extra={"event_data": {"code": error.code, "path": request.url.path}})
    return error_response(error, request_id=request_id)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    """Orice exceptie care nu e un AppError (deja tratat mai sus) — fara handler
    explicit, Starlette ar raspunde cu text simplu, fara nimic util pentru
    frontend/loguri. Logam traceback-ul complet, raspundem cu plicul standard."""
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    logger.exception("unexpected_error", extra={"event_data": {"path": request.url.path}})
    return error_response(
        AppError("A aparut o eroare neasteptata pe server."), request_id=request_id
    )


# /assistant/* (persistenta conversatiilor, compresie, atasamente, voce) ramane
# suprafata de chat pentru interfata — foloseste orchestratorul+financial_advisor-ul
# lui Cristi doar ca "creier" in interiorul agentului financial_advisor (vezi
# agents/financial_advisor.py), nu ca ruta separata.
#
# agents/alerte/admin/profiles sunt totusi inregistrate, sub /api/v1, ca ml-neregularitati
# le foloseste direct (rapoarte de administrator, alerte pentru utilizator, proxy-ul
# generic din frontend/src/app/api/backend/[...path]/route.ts) si testele lor pornesc
# aplicatia reala prin TestClient(app). /api/v1/agents/chat ramane o a doua suprafata de
# chat, neexpusa din interfata (frontend-ul asistentului vorbeste doar cu /assistant/*).
app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")
app.include_router(assistant.router)
app.include_router(identity.router)
# Revizuirea manuala a verificarilor de identitate. Isi tine prefixul propriu
# (/api/identity/admin) in router, langa rutele de identitate pe care le revizuieste.
app.include_router(admin_identity_router)
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(alerte.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(credite.router, prefix="/api/v1")
app.include_router(credite.router_admin, prefix="/api/v1")
