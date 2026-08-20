import os

os.environ.setdefault("SUPABASE_URL", "http://supabase.invalid")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["body"]["environment"]
    assert response.headers["x-request-id"]


def test_health_bare_path_matches() -> None:
    """Inregistrat de doua ori (bare + /api/v1), acelasi continut in ambele."""
    client = TestClient(app)
    assert client.get("/health").json()["body"] == client.get("/api/v1/health").json()["body"]
