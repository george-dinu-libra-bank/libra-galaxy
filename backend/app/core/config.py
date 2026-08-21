"""Singurul modul care citeste variabile de mediu (ARCHITECTURE.md #14, SECURITY.md #4)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _empty_string_to_none(value: object) -> object:
    """`.env` cu o cheie prezenta dar goala (IDENTITY_VERIFY_DISTANCE_THRESHOLD=)
    trebuie tratat ca "nesetat", nu ca "" de parsat ca float — altfel Settings()
    arunca ValidationError la pornire in loc sa foloseasca default=None."""
    return None if value == "" else value


OptionalFloat = Annotated[float | None, BeforeValidator(_empty_string_to_none)]

_REPO_ROOT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "galaxy-bank-knowledge"
# Sursa unica de credentiale a proiectului (vezi .env.example la radacina) —
# nu backend/.env. Cale absoluta, nu relativa la CWD: functioneaza identic
# rulat din backend/ (uvicorn local), din radacina, sau in Docker (unde
# oricum docker-compose injecteaza variabilele direct ca environment, care
# au prioritate fata de orice fisier citit aici).
_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = Field(default="local", alias="ENVIRONMENT")

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    # Cheia "secret" (sb_secret_...), nu "publishable" (sb_publishable_...) —
    # doar cea secreta ocoleste RLS. Nu exista SUPABASE_JWT_SECRET: proiectul
    # semneaza token-uri cu ES256 (chei asimetrice, verificat live prin
    # /auth/v1/.well-known/jwks.json), nu cu un secret HS256 partajat
    # (core/security.py verifica prin JWKS, nu printr-un secret static).
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    # Cheia publica/anon — folosita ca sa se construiasca un client scopat pe
    # utilizator (create_user_client), care pastreaza contextul RLS in loc sa
    # ocoleasca RLS ca service-role. Vezi agents/financial_advisor.py: orchestratorul
    # lui Cristi si AnalizaService citesc prin acest client, nu prin service_role.
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")

    # Endpoint-ul Foundry ("Models" blade, forma .../models) e compatibil OpenAI
    # direct prin base_url — nu e nevoie de api_version (providers/foundry.py).
    foundry_endpoint: str = Field(default="", alias="AZURE_FOUNDRY_ENDPOINT")
    foundry_api_key: str = Field(default="", alias="AZURE_FOUNDRY_API_KEY")
    foundry_chat_deployment: str = Field(default="gpt-5-mini", alias="AZURE_FOUNDRY_CHAT_DEPLOYMENT")
    foundry_embedding_deployment: str = Field(
        default="text-embedding-3-small", alias="AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT"
    )
    # Generos in mod deliberat: gpt-5-mini e un model de reasoning si tokenii de
    # reasoning se scad din acelasi buget ca raspunsul vizibil (verificat live —
    # un "OK" a consumat intre 64 si 128 tokeni de reasoning).
    foundry_max_completion_tokens: int = Field(default=2000, alias="AZURE_FOUNDRY_MAX_COMPLETION_TOKENS")
    embedding_version: str = Field(default="v1", alias="LIBRA_EMBEDDING_VERSION")

    chat_price_per_million_input: float = Field(default=0.25, alias="LIBRA_AI_CHAT_PRICE_PER_MILLION_INPUT")
    chat_price_per_million_output: float = Field(default=2.0, alias="LIBRA_AI_CHAT_PRICE_PER_MILLION_OUTPUT")

    # Agentul vocal foloseste Azure AI Speech, un serviciu separat de Foundry
    # (chat/embeddings) dar din acelasi tenant Azure — vezi PROJECT_CONTEXT.md #33.
    speech_endpoint: str = Field(default="", alias="AZURE_SPEECH_ENDPOINT")
    speech_key: str = Field(default="", alias="AZURE_SPEECH_KEY")
    speech_region: str = Field(default="", alias="AZURE_SPEECH_REGION")
    speech_voice_name: str = Field(default="ro-RO-AlinaNeural", alias="AZURE_SPEECH_VOICE_NAME")

    # Atasamente in chat (PDF/poze) — bucket privat in Supabase Storage.
    attachments_bucket: str = Field(default="asistent-atasamente", alias="LIBRA_ATTACHMENTS_BUCKET")
    max_attachment_bytes: int = Field(default=10 * 1024 * 1024, alias="LIBRA_MAX_ATTACHMENT_BYTES")

    # Exporturi PDF generate de aplicatie (nu incarcate de utilizator) — bucket
    # privat separat, fiindca whitelist-ul/RLS-ul de mai sus e gandit pentru input.
    export_bucket: str = Field(default="asistent-exporturi", alias="LIBRA_EXPORT_BUCKET")
    export_signed_url_seconds: int = Field(default=900, alias="LIBRA_EXPORT_URL_SECONDS")

    # Explicit, nu dedus din adancimea fisierului (fragil intre local si Docker).
    # Local: repo_root/galaxy-bank-knowledge. In container: vezi docker-compose.yml,
    # unde folderul e montat direct la /galaxy-bank-knowledge.
    knowledge_dir: str = Field(default="", alias="LIBRA_KNOWLEDGE_DIR")

    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Verificare identitate la inregistrare (OCR buletin + DeepFace selfie).
    # Secret partajat doar intre serverul Next.js si acest serviciu, folosit
    # cand nu exista inca o sesiune Supabase (vezi core/security.py
    # get_principal_or_internal si api/routes/identity.py).
    backend_internal_api_key: str = Field(default="", alias="BACKEND_INTERNAL_API_KEY")
    # None => se foloseste pragul implicit al modelului ArcFace din DeepFace.
    identity_verify_distance_threshold: OptionalFloat = Field(
        default=None, alias="IDENTITY_VERIFY_DISTANCE_THRESHOLD"
    )
    identity_deepface_model: str = Field(default="ArcFace", alias="IDENTITY_DEEPFACE_MODEL")
    # yunet: detector DNN mic (parte din opencv), mult mai fiabil decat Haar
    # cascade-ul default ("opencv") pe poze mici/inclinate ca fotografia din
    # buletin. Fara dependente noi — greutatile se descarca automat de DeepFace.
    identity_detector_backend: str = Field(default="yunet", alias="IDENTITY_DETECTOR_BACKEND")

    # Financial advisor-ul lui Cristi (agents/financiar.py) — bucla proprie de
    # tool-calling peste azure-ai-inference, cu propriile praguri de siguranta.
    llm_provider: str = Field(default="azure", alias="LLM_PROVIDER")
    azure_ai_endpoint: str = Field(default="", alias="AZURE_AI_ENDPOINT")
    # 'key' merge oriunde, inclusiv in container. 'identity' foloseste Entra
    # prin DefaultAzureCredential (az login local, sau managed identity in Azure).
    azure_ai_auth: str = Field(default="key", alias="AZURE_AI_AUTH")
    azure_ai_api_key: str = Field(default="", alias="AZURE_AI_API_KEY")
    azure_ai_chat_deployment: str = Field(default="gpt-5-mini", alias="AZURE_AI_CHAT_DEPLOYMENT")
    azure_ai_embedding_deployment: str = Field(
        default="text-embedding-3-small", alias="AZURE_AI_EMBEDDING_DEPLOYMENT"
    )
    agent_max_tokens: int = Field(default=4000, alias="AGENT_MAX_TOKENS")
    # Un pas = un raspuns al modelului. Plasa de siguranta, nu tinta.
    agent_max_pasi: int = Field(default=10, alias="AGENT_MAX_PASI")
    # Cate tranzactii se citesc cel mult pentru o analiza (AnalizaService).
    analiza_limita_randuri: int = Field(default=1000, alias="ANALIZA_LIMITA_RANDURI")

    @property
    def agenti_activi(self) -> bool:
        if not self.azure_ai_endpoint:
            return False
        return self.azure_ai_auth.lower() == "identity" or bool(self.azure_ai_api_key)

    @property
    def embedding_key(self) -> str:
        return f"foundry:{self.foundry_embedding_deployment}:{self.embedding_version}"

    @property
    def foundry_configured(self) -> bool:
        return bool(self.foundry_endpoint and self.foundry_api_key)

    @property
    def speech_configured(self) -> bool:
        return bool(self.speech_key and (self.speech_endpoint or self.speech_region))

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def knowledge_dir_path(self) -> Path:
        return Path(self.knowledge_dir) if self.knowledge_dir else _REPO_ROOT_KNOWLEDGE_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
