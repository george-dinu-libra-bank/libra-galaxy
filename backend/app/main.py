import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import agents, alerte, health, identity, profiles
from app.infrastructure.config import get_settings
from app.infrastructure.logging import obtine_logger

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = obtine_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "Idempotency-Key",
        "X-Internal-Api-Key",
        "X-User-Id",
    ],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def eroare_neasteptata(request: Request, exc: Exception) -> JSONResponse:
    """
    Orice exceptie necatalogata (nu ErrorAplicatie, care e deja prinsa la nivel
    de ruta) ajunge aici — fara handler explicit, Starlette raspunde cu text
    simplu "Internal Server Error", fara nimic util in el pentru frontend/loguri.
    Aici o logam complet (traceback in consola backend-ului) si raspundem cu un
    cod stabil, ca sa se stie macar ca a fost o eroare neprevazuta, nu una din
    cazurile tratate explicit.
    """
    logger.exception("eroare_neasteptata: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        # Aceeasi forma ca detail={"cod":..., "mesaj":...} de la HTTPException
        # (vezi routes/identity.py), ca frontend-ul sa citeasca uniform response.detail.
        content={
            "detail": {
                "cod": "eroare_neasteptata",
                "mesaj": "A aparut o eroare neasteptata pe server.",
            }
        },
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(alerte.router, prefix="/api/v1")
# Fara prefix: routerul isi poarta propriul /api/identity, iar frontendul
# cheama exact acel path (vezi frontend/src/lib/actions/identitate.ts).
app.include_router(identity.router)
