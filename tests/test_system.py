from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check_is_lightweight_and_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_reports_healthy_dependencies(monkeypatch):
    class FakeConnection:
        async def execute(self, statement):
            return None

    class FakeEngineConnection:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class FakeEngine:
        def connect(self):
            return FakeEngineConnection()

    async def fake_ping():
        return True

    monkeypatch.setattr("app.main.engine", FakeEngine())
    monkeypatch.setattr("app.main.redis.ping", fake_ping)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"database": "ok", "redis": "ok"},
    }
