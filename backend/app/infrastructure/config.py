from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurarea intregului backend (vezi backend/.env.example).

    Aplicatia are doua parti crescute separat si unite aici: verificarea
    identitatii (OCR + DeepFace) si layerul de agenti cu detectia de
    neregularitati. Fiecare isi are cheile ei, iar niciuna nu e obligatorie la
    pornire: lipsa unei chei opreste doar functia care depinde de ea, nu tot
    serviciul. De aceea campurile au valori implicite goale in loc sa fie
    cerute — un backend care nu porneste deloc pentru ca lipseste o cheie de
    OCR ar lua cu el si alertele, care n-au nevoie de ea.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Libra API"
    app_env: str = "development"
    log_level: str = "INFO"

    # --- Supabase -----------------------------------------------------------
    supabase_url: str
    # Cheia publica: cu ea se construieste clientul per-utilizator, deci RLS
    # ramane bariera din baza de date.
    supabase_anon_key: str = ""
    # Cheia privilegiata: trece peste RLS. Numai pentru scrieri de serviciu
    # (verificare identitate), niciodata pentru citiri in numele cuiva.
    supabase_service_role_key: str = ""

    # Secret partajat doar intre serverul Next.js si acest serviciu, folosit
    # cand nu exista inca o sesiune Supabase (inregistrare cu confirmare pe
    # email activata) — vezi app/api/dependencies.py.
    backend_internal_api_key: str = ""

    # Acceptam ambele nume: CORS_ALLOW_ORIGINS venea cu partea de identitate,
    # CORS_ORIGINS cu cea de agenti. Le pastram pe amandoua ca sa nu ceara
    # nimanui sa isi rescrie .env-ul dupa unificare.
    cors_allow_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ALLOW_ORIGINS", "CORS_ORIGINS"),
    )

    # --- Verificare identitate ---------------------------------------------
    # None => pragul implicit al modelului ArcFace din DeepFace.
    identity_verify_distance_threshold: float | None = None
    identity_deepface_model: str = "ArcFace"
    # yunet: detector DNN mic (parte din opencv), mult mai fiabil decat Haar
    # cascade-ul default ("opencv") pe poze mici/inclinate ca fotografia din
    # buletin. Fara dependente noi — greutatile se descarca automat de DeepFace.
    identity_detector_backend: str = "yunet"

    # --- Layerul de agenti --------------------------------------------------
    # Fara credentiale, chatul raspunde 503; alertele merg oricum.
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

    @property
    def agenti_activi(self) -> bool:
        if not self.azure_ai_endpoint:
            return False
        return self.azure_ai_auth.lower() == "identity" or bool(self.azure_ai_api_key)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def supabase_jwks_url(self) -> str:
        """Cheile publice de semnare JWT ale proiectului — Supabase foloseste acum chei
        asimetrice (ECC/RSA), nu un secret simetric legacy, deci verificarea se face
        prin JWKS, fara niciun secret suplimentar in .env."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
