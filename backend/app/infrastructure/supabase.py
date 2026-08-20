from functools import lru_cache

from supabase import Client, create_client

from app.infrastructure.config import get_settings


@lru_cache
def get_admin_client() -> Client:
    """Client Supabase cu service-role key — bypass RLS, ca in frontend/src/lib/supabase/admin.js."""
    setari = get_settings()
    return create_client(setari.supabase_url, setari.supabase_service_role_key)
