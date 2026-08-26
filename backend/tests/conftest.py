import os

# Setarile sunt obligatorii la import; testele nu ating Supabase-ul real.
os.environ.setdefault("SUPABASE_URL", "http://supabase.invalid")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

# Azure Document Intelligence se stinge pentru toata suita.
#
# Nu `setdefault`: in container cheile chiar EXISTA, venite din .env prin
# docker-compose, iar fara linia asta fiecare test care incarca o adeverinta
# chema API-ul pe bune. S-a vazut imediat — suita a sarit de la 26 la 95 de
# secunde — dar partea care nu se vede e ca fiecare rulare costa bani si
# depinde de o resursa externa ca sa treaca.
#
# Cine vrea sa testeze chiar drumul prin Azure il pune la loc explicit, cu un
# client fals (vezi tests/test_document_intelligence.py).
os.environ["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"] = ""
os.environ["AZURE_DOCUMENT_INTELLIGENCE_KEY"] = ""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
