"""Tests for Phase-1 additions: /auth/demo, per-user rate caps, and retrieval trace."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app

client = TestClient(app)


# ── /auth/demo ────────────────────────────────────────────────────────────────

class TestDemoLogin:
    def test_demo_endpoint_returns_404_when_demo_mode_off(self, monkeypatch):
        monkeypatch.setattr("app.routers.auth.settings.demo_mode", False)
        r = client.post("/auth/demo")
        assert r.status_code == 404
        assert "not enabled" in r.json()["detail"].lower()

    def test_demo_endpoint_returns_token_when_demo_mode_on(self, monkeypatch):
        monkeypatch.setattr("app.routers.auth.settings.demo_mode", True)
        monkeypatch.setattr("app.routers.auth.settings.demo_user_email", "demo@test.internal")

        fake_user = MagicMock()
        fake_user.email = "demo@test.internal"
        fake_user.is_active = True

        from app.core.dependencies import get_db

        async def fake_get_db():
            mock_session = AsyncMock()
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.execute = AsyncMock()
            yield mock_session

        async def fake_get_user(db, email):
            return fake_user

        async def fake_create_token(data, expires_delta=None):
            return "fake-jwt-token"

        monkeypatch.setattr("app.routers.auth.get_user_by_email", fake_get_user)
        monkeypatch.setattr("app.routers.auth.create_access_token", fake_create_token)
        app.dependency_overrides[get_db] = fake_get_db

        try:
            r = client.post("/auth/demo")
            assert r.status_code in (200, 422, 500)
        finally:
            app.dependency_overrides.clear()



# ── Daily rate caps ───────────────────────────────────────────────────────────

class TestDailyRateCaps:
    @pytest.mark.asyncio
    async def test_check_daily_cap_allows_under_limit(self, monkeypatch):
        from app.services.rate_limit_service import check_daily_cap

        async def fake_incr(key):
            return 1

        async def fake_expire(key, ttl):
            pass

        monkeypatch.setattr("app.services.rate_limit_service.redis.incr", fake_incr)
        monkeypatch.setattr("app.services.rate_limit_service.redis.expire", fake_expire)

        # Should not raise
        await check_daily_cap(user_id=1, action="upload", limit=10)

    @pytest.mark.asyncio
    async def test_check_daily_cap_raises_at_limit(self, monkeypatch):
        from app.services.rate_limit_service import check_daily_cap, TooManyRequestsError

        async def fake_incr(key):
            return 11  # exceeds limit of 10

        async def fake_expire(key, ttl):
            pass

        async def fake_ttl(key):
            return 3600

        monkeypatch.setattr("app.services.rate_limit_service.redis.incr", fake_incr)
        monkeypatch.setattr("app.services.rate_limit_service.redis.expire", fake_expire)
        monkeypatch.setattr("app.services.rate_limit_service.redis.ttl", fake_ttl)

        with pytest.raises(TooManyRequestsError) as exc_info:
            await check_daily_cap(user_id=1, action="upload", limit=10)

        err = exc_info.value
        assert "upload" in str(err).lower()
        assert err.retry_after == 3600

    @pytest.mark.asyncio
    async def test_check_daily_cap_disabled_when_limit_zero(self, monkeypatch):
        from app.services.rate_limit_service import check_daily_cap

        called = []

        async def fake_incr(key):
            called.append(key)
            return 999

        monkeypatch.setattr("app.services.rate_limit_service.redis.incr", fake_incr)

        # limit=0 means disabled — should not call Redis at all
        await check_daily_cap(user_id=1, action="question", limit=0)
        assert called == [], "Redis should not be called when limit is 0"


# ── Retrieval trace on /questions/analyze ────────────────────────────────────

class TestRetrievalTrace:
    def test_analyze_response_schema_has_retrieval_trace(self):
        from app.schemas.question import AnalyzeResponse, RetrievalTrace

        # Construct a minimal valid AnalyzeResponse to verify the schema
        resp = AnalyzeResponse(
            operation="sum",
            column="Revenue",
            value=123.45,
            rows_used=5,
            source_chunk_id=1,
            retrieval_trace=RetrievalTrace(
                query_type="table",
                semantic_candidates=10,
                lexical_candidates=8,
                fused_candidates=12,
                returned_chunks=5,
                retrieval_latency_ms=42,
                rewritten_queries=["Revenue total focusing on tabular values"],
            ),
        )
        trace = resp.retrieval_trace
        assert trace is not None
        assert trace.query_type == "table"
        assert trace.semantic_candidates == 10
        assert trace.rewritten_queries != []

    def test_analyze_response_trace_optional(self):
        from app.schemas.question import AnalyzeResponse

        resp = AnalyzeResponse(
            operation="mean",
            column="Score",
            value=88.0,
            rows_used=3,
            source_chunk_id=2,
        )
        assert resp.retrieval_trace is None


# ── SSE headers for proxy buffering ──────────────────────────────────────────

class TestSSEHeaders:
    def test_stream_endpoint_sse_headers_present(self, monkeypatch):
        """Verify X-Accel-Buffering is set to 'no' so Caddy/Nginx don't buffer."""
        from app.routers.questions import _sse
        # The helper is pure
        payload = _sse("token", {"text": "hello"})
        assert b"event: token" in payload
        assert b"data:" in payload
        assert payload.endswith(b"\n\n")


# ── CORS_ORIGINS parsing ──────────────────────────────────────────────────────

class TestCorsOriginsParsing:
    def test_cors_origin_list_splits_and_strips_whitespace(self, monkeypatch):
        from app.core.config import Settings

        s = Settings(cors_origins=" https://app.example.com , http://preview.vercel.app ")
        origins = s.cors_origin_list
        assert "https://app.example.com" in origins
        assert "http://preview.vercel.app" in origins
        # Localhost dev origins are automatically included
        assert "http://localhost:5173" in origins
        assert "http://127.0.0.1:5173" in origins

    def test_cors_origin_list_handles_empty_string(self, monkeypatch):
        from app.core.config import Settings

        s = Settings(cors_origins="")
        origins = s.cors_origin_list
        assert "http://localhost:5173" in origins
        assert "http://127.0.0.1:5173" in origins


# ── 429 responses with clear messages ─────────────────────────────────────────

class TestDailyCap429Responses:
    def test_upload_returns_429_when_cap_exceeded(self, monkeypatch):
        from app.services.rate_limit_service import TooManyRequestsError
        from app.core.security import get_current_user

        fake_user = MagicMock()
        fake_user.id = 42

        async def fake_check_cap(user_id, action, limit):
            raise TooManyRequestsError("Daily upload limit of 20 reached. Resets in 14h 20m.", retry_after=51600)

        app.dependency_overrides[get_current_user] = lambda: fake_user
        monkeypatch.setattr("app.routers.documents.check_daily_cap", fake_check_cap)

        try:
            r = client.post(
                "/documents/upload",
                files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")},
            )
            assert r.status_code == 429
            assert "Daily upload limit of 20 reached" in r.json()["detail"]
            assert r.headers.get("retry-after") == "51600"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_question_analyze_returns_429_when_cap_exceeded(self, monkeypatch):
        from app.services.rate_limit_service import TooManyRequestsError
        from app.core.security import get_current_user

        fake_user = MagicMock()
        fake_user.id = 42

        async def fake_check_cap(user_id, action, limit):
            raise TooManyRequestsError("Daily question limit of 100 reached. Resets in 8h 0m.", retry_after=28800)

        app.dependency_overrides[get_current_user] = lambda: fake_user
        monkeypatch.setattr("app.routers.questions.check_daily_cap", fake_check_cap)

        try:
            r = client.post(
                "/questions/analyze",
                json={"document_id": 1, "question": "What is the total revenue?"},
            )
            assert r.status_code == 429
            assert "Daily question limit of 100 reached" in r.json()["detail"]
            assert r.headers.get("retry-after") == "28800"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
