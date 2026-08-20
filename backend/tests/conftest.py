import os

# Setarile sunt obligatorii la import; testele nu ating Supabase-ul real.
os.environ.setdefault("SUPABASE_URL", "http://supabase.invalid")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
