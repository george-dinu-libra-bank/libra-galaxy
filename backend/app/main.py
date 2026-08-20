from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.identity import router as identity_router
from app.infrastructure.config import get_settings
from app.infrastructure.logging import configureaza_logging, obtine_logger

configureaza_logging()
logger = obtine_logger(__name__)

app = FastAPI(title="Libra API", version="0.1.0")


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
        content={"detail": {"cod": "eroare_neasteptata", "mesaj": "A aparut o eroare neasteptata pe server."}},
    )

setari = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=setari.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(identity_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
