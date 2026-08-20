from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import assistant, health, identity
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
    allow_methods=["*"],
    allow_headers=["*"],
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


# Routerele lui Cristi (agents, alerte, profiles) exista in backend/app/api/routes/
# dar nu sunt inregistrate aici inca — decizia de azi a fost sa pastram
# /assistant/* (persistenta conversatiilor, compresie, atasamente, voce) ca
# suprafata unica, si sa folosim doar orchestratorul+financial_advisor-ul lui
# Cristi ca "creier" in interiorul agentului financial_advisor (vezi
# agents/financial_advisor.py). Inregistrarea lor separata ramane de discutat.
app.include_router(health.router)
app.include_router(assistant.router)
app.include_router(identity.router)
