from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
