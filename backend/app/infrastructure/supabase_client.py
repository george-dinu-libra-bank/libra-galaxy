"""Singurul modul care importa supabase-py (paralela cu regula Mongo din docs/DATABASE.md).

Repository-urile primesc clientul de aici, niciodata construindu-l singure.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings
from app.core.errors import ConfigurationError


@lru_cache
def get_service_client() -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise ConfigurationError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY nu sunt configurate.")

    return create_client(settings.supabase_url, settings.supabase_service_role_key)
