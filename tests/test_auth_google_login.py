from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.routers import auth


client = TestClient(app)


def test_google_login_redirects_to_google_with_state(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client-id", raising=False)
    monkeypatch.setattr(settings, "google_client_secret", "test-client-secret", raising=False)
    monkeypatch.setattr(settings, "google_redirect_uri", "https://web-production-1e529.up.railway.app/auth/google/callback", raising=False)

    async def fake_set_cache(*args, **kwargs):
        return None

    monkeypatch.setattr(auth, "set_cache", fake_set_cache)

    response = client.get(
        "/auth/google/login",
        follow_redirects=False,
    )

    assert response.status_code == 307
    redirect_url = response.headers["location"]
    assert redirect_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "state=" in redirect_url
