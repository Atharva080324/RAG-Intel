from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check_is_lightweight_and_available():
    import time

    start = time.perf_counter()
    response = client.get("/health")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert elapsed < 2.0, f"/health took {elapsed:.3f}s, exceeding 2s limit"


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
    data = response.json()
    assert data["status"] in ("ready", "warming_up")
    assert data["dependencies"] == {"database": "ok", "redis": "ok"}
    assert "warmed_up" in data

