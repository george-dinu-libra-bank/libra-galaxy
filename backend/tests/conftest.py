import os

# Setarile sunt obligatorii la import; testele nu ating Supabase-ul real.
os.environ.setdefault("SUPABASE_URL", "http://supabase.invalid")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
# Si cheia de service_role: get_service_client() (infrastructure/supabase_client.py)
# arunca ConfigurationError daca lipseste, iar rutele care ajung la ea raspund
# cu 500 inainte sa apuce sa faca ceva. Clientul se construieste, dar nu pleaca
# nicio cerere: repository-urile sunt oricum inlocuite in teste.
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

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


@pytest.fixture(autouse=True)
def limitator_curat():
    """Limitatorul de rata tine starea intr-un dict la nivel de modul.

    Fara curatenie intre teste, ordinea lor decide daca trec: un fisier care
    incarca zece documente consuma limita si pica fisierul urmator — si o face
    doar cand suita ruleaza intreaga, nu cand rulezi testul singur. Exact asa
    s-a manifestat: 27 de teste rosii in suita, toate verzi luate separat.

    Autouse la nivel de conftest, nu in fiecare fisier: starea e globala, deci
    si curatenia trebuie sa fie.
    """
    from app.infrastructure import rate_limit

    rate_limit._INCERCARI.clear()
    yield
    rate_limit._INCERCARI.clear()
