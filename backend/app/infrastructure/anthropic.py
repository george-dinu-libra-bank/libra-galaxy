from functools import lru_cache

from anthropic import AsyncAnthropic

from app.infrastructure.config import get_settings


@lru_cache
def get_anthropic_client() -> AsyncAnthropic:
    """Client partajat pe proces. Cheia sta doar aici, pe server."""
    return AsyncAnthropic(api_key=get_settings().anthropic_api_key)
