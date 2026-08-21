from functools import lru_cache

from supabase import Client, create_client

from app.infrastructure.config import Settings, get_settings


def create_user_client(settings: Settings, access_token: str) -> Client:
    """Client legat de sesiunea utilizatorului, deci RLS filtreaza in baza de date.

    Asta e clientul implicit pentru citiri: chiar daca o verificare din cod ar
    fi gresita, politicile raman a doua bariera.
    """
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client


def create_auth_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache
def get_admin_client() -> Client:
    """Client Supabase cu service-role key — bypass RLS, ca in frontend/src/lib/supabase/admin.js.

    Folosit doar de verificarea de identitate (scrierile inainte sa existe o
    sesiune) si de citirile panoului de administrator. Fiindca ocoleste
    politicile, orice ruta care il foloseste trebuie sa faca ea insasi
    verificarea de drepturi (cere_administrator): baza de date nu o mai face
    in locul ei. Restul backendului merge prin clientii de mai sus, ca sa
    pastreze contextul RLS al utilizatorului.
    """
    setari = get_settings()
    return create_client(setari.supabase_url, setari.supabase_service_role_key)
