from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurare incarcata din environment (vezi backend/.env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str

    # Secret partajat doar intre serverul Next.js si acest serviciu, folosit
    # cand nu exista inca o sesiune Supabase (inregistrare cu confirmare pe
    # email activata) — vezi app/api/dependencies.py.
    backend_internal_api_key: str

    # Originile frontend-ului, separate prin virgula.
    cors_allow_origins: str = "http://localhost:3000"

    # None => se foloseste pragul implicit al modelului ArcFace din DeepFace.
    identity_verify_distance_threshold: float | None = None

    identity_deepface_model: str = "ArcFace"
    # yunet: detector DNN mic (parte din opencv), mult mai fiabil decat Haar
    # cascade-ul default ("opencv") pe poze mici/inclinate ca fotografia din
    # buletin. Fara dependente noi — greutatile se descarca automat de DeepFace.
    identity_detector_backend: str = "yunet"

    @property
    def cors_origins(self) -> list[str]:
        return [origine.strip() for origine in self.cors_allow_origins.split(",") if origine.strip()]

    @property
    def supabase_jwks_url(self) -> str:
        """Cheile publice de semnare JWT ale proiectului — Supabase foloseste acum chei
        asimetrice (ECC/RSA), nu un secret simetric legacy, deci verificarea se face
        prin JWKS, fara niciun secret suplimentar in .env."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
