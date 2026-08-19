from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.infrastructure.config import Settings, get_settings
from app.main import app

UTILIZATOR = UserContext(user_id=uuid4(), access_token="token-de-test")


def _setari(**suprascrieri) -> Settings:
    baza = {
        "supabase_url": "http://supabase.invalid",
        "supabase_anon_key": "test-anon-key",
    }
    return Settings(**{**baza, **suprascrieri})


def test_chat_cere_autentificare() -> None:
    response = TestClient(app).post("/api/v1/agents/chat", json={"mesaj": "cat am in cont?"})

    assert response.status_code == 401


def test_chat_raspunde_503_fara_cheie_anthropic() -> None:
    app.dependency_overrides[get_current_user] = lambda: UTILIZATOR
    app.dependency_overrides[get_user_supabase] = lambda: object()
    app.dependency_overrides[get_settings] = lambda: _setari(anthropic_api_key="")

    try:
        response = TestClient(app).post("/api/v1/agents/chat", json={"mesaj": "cat am in cont?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_chat_refuza_campuri_in_plus() -> None:
    app.dependency_overrides[get_current_user] = lambda: UTILIZATOR
    app.dependency_overrides[get_user_supabase] = lambda: object()
    app.dependency_overrides[get_settings] = lambda: _setari(anthropic_api_key="cheie")

    try:
        # user_id nu are voie sa vina de la client: identitatea se ia din token.
        response = TestClient(app).post(
            "/api/v1/agents/chat",
            json={"mesaj": "cat am in cont?", "user_id": str(uuid4())},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
