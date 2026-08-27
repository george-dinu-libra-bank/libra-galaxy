import os

# Setarile sunt obligatorii la import; testele nu ating Supabase-ul real.
os.environ.setdefault("SUPABASE_URL", "http://supabase.invalid")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
# Si cheia de service_role: get_service_client() (infrastructure/supabase_client.py)
# arunca ConfigurationError daca lipseste, iar rutele care ajung la ea raspund
# cu 500 inainte sa apuce sa faca ceva. Clientul se construieste, dar nu pleaca
# nicio cerere: repository-urile sunt oricum inlocuite in teste.
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
