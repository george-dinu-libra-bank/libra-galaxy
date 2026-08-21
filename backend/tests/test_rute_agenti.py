from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.config import Settings, get_settings
from app.main import app

UTILIZATOR = UserContext(user_id=uuid4(), access_token="token-de-test")


def _setari(**suprascrieri) -> Settings:
    return Settings(
        supabase_url="http://supabase.invalid",
        supabase_anon_key="test-anon-key",
        **suprascrieri,
    )


def _cu_utilizator_fals(**setari):
    app.dependency_overrides[get_current_user] = lambda: UTILIZATOR
    app.dependency_overrides[get_user_supabase] = lambda: object()
    app.dependency_overrides[get_settings] = lambda: _setari(**setari)


def test_chatul_cere_autentificare() -> None:
    raspuns = TestClient(app).post("/api/v1/agents/chat", json={"mesaj": "cat am in cont?"})

    assert raspuns.status_code == 401


def test_alertele_cer_autentificare() -> None:
    assert TestClient(app).get("/api/v1/alerte").status_code == 401


def test_chatul_raspunde_503_fara_credentiale() -> None:
    _cu_utilizator_fals(azure_ai_endpoint="", azure_ai_api_key="")
    try:
        raspuns = TestClient(app).post("/api/v1/agents/chat", json={"mesaj": "cat am?"})
    finally:
        app.dependency_overrides.clear()

    assert raspuns.status_code == 503


def test_identitatea_nu_poate_veni_de_la_client() -> None:
    _cu_utilizator_fals(azure_ai_endpoint="https://exemplu.invalid", azure_ai_api_key="cheie")
    try:
        raspuns = TestClient(app).post(
            "/api/v1/agents/chat",
            json={"mesaj": "cat am?", "user_id": str(uuid4())},
        )
    finally:
        app.dependency_overrides.clear()

    assert raspuns.status_code == 422
