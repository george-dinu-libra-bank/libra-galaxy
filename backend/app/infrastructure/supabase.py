from supabase import Client, create_client

from app.infrastructure.config import Settings


def create_user_client(settings: Settings, access_token: str) -> Client:
    """Create a request-scoped client that keeps the user's RLS context."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client


def create_auth_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)
