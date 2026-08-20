from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, agents, alerte, health, profiles
from app.api.routes.admin_identity import router as admin_identity_router
from app.api.routes.identity import router as identity_router
from app.infrastructure.config import get_settings
from app.infrastructure.logging import configureaza_logging, obtine_logger

configureaza_logging()
logger = obtine_logger(__name__)

setari = get_settings()

app = FastAPI(
    title=setari.app_name,
    version="0.1.0",
    docs_url="/docs" if setari.app_env != "production" else None,
    redoc_url=None,
)


@app.exception_handler(Exception)
async def eroare_neasteptata(request: Request, exc: Exception) -> JSONResponse:
    """
    Orice exceptie necatalogata (nu ErrorAplicatie, care e deja prinsa la
    nivel de ruta) ajunge aici — fara handler explicit, Starlette raspunde cu
    text simplu "Internal Server Error", fara nimic util in el pentru
    frontend/loguri. Aici o logam complet (traceback in consola backend-ului)
    si raspundem cu un cod stabil, ca sa se stie macar ca a fost o eroare
    neprevazuta, nu una din cazurile tratate explicit.
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=setari.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key",
                   "X-Internal-Api-Key", "X-User-Id"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Verificarea identitatii isi pastreaza prefixul propriu (/api/identity/...),
# fixat in router; restul stau sub /api/v1.
app.include_router(identity_router)
app.include_router(admin_identity_router)
app.include_router(health.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(alerte.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health")
def health_scurt() -> dict[str, str]:
    """Pastrat pentru healthcheck-ul din compose, pe langa /api/v1/health."""
    return {"status": "ok"}
