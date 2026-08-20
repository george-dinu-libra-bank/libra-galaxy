from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurare incarcata din environment (vezi backend/.env.example)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Libra API"
    app_env: str = "development"
    log_level: str = "INFO"
    supabase_url: str
    supabase_anon_key: str
    cors_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )

    # Cheia de service-role. Optionala pentru ca restul backendului merge fara ea
    # (agentii si alertele folosesc contextul RLS al utilizatorului); doar
    # verificarea de identitate o cere, fiindca scrie inainte sa existe sesiune.
    supabase_service_role_key: str = ""

    # Secret partajat doar intre serverul Next.js si acest serviciu, folosit cand
    # nu exista inca o sesiune Supabase (inregistrare cu confirmare pe email
    # activata) — vezi app/api/dependencies.py. Lasat gol, calea cu cheie interna
    # ramane inchisa si autentificarea merge doar prin JWT.
    backend_internal_api_key: str = ""

    # Layer-ul de agenti. Fara credentiale, chatul raspunde 503; alertele merg.
    llm_provider: str = "azure"
    azure_ai_endpoint: str = ""
    # 'key' merge oriunde, inclusiv in container. 'identity' foloseste Entra prin
    # DefaultAzureCredential: az login local, sau managed identity cand rulezi in Azure.
    azure_ai_auth: str = "key"
    azure_ai_api_key: str = ""
    azure_ai_chat_deployment: str = "gpt-5-mini"
    azure_ai_embedding_deployment: str = "text-embedding-3-small"
    agent_max_tokens: int = 4000
    # Un pas = un raspuns al modelului. Plasa de siguranta, nu tinta.
    agent_max_pasi: int = 10
    # Cate tranzactii se citesc cel mult pentru o analiza.
    analiza_limita_randuri: int = 1000

    # Verificarea de identitate la inregistrare (buletin OCR + selfie).
    # None => se foloseste pragul implicit al modelului ArcFace din DeepFace.
    identity_verify_distance_threshold: float | None = None
    identity_deepface_model: str = "ArcFace"
    # yunet: detector DNN mic (parte din opencv), mult mai fiabil decat Haar
    # cascade-ul default ("opencv") pe poze mici/inclinate ca fotografia din
    # buletin. Fara dependente noi — greutatile se descarca automat de DeepFace.
    identity_detector_backend: str = "yunet"

    @property
    def agenti_activi(self) -> bool:
        if not self.azure_ai_endpoint:
            return False
        return self.azure_ai_auth.lower() == "identity" or bool(self.azure_ai_api_key)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def supabase_jwks_url(self) -> str:
        """Cheile publice de semnare JWT ale proiectului — Supabase foloseste acum chei
        asimetrice (ECC/RSA), nu un secret simetric legacy, deci verificarea se face
        prin JWKS, fara niciun secret suplimentar in .env."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
