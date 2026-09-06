from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fieldops.agent.checkpointer import get_checkpointer, reset_checkpointer
from fieldops.core.config import Settings
from fieldops.main import app


client = TestClient(app)


class TestProductionSettingsGuards:
    """Verify security and reliability configuration guards for production environments."""

    def test_production_rejects_debug_mode(self) -> None:
        with pytest.raises(ValidationError, match="DEBUG mode cannot be enabled in production"):
            Settings(
                APP_ENV="production",
                DEBUG=True,
                CHECKPOINTER_BACKEND="postgres",
                WEBHOOK_SHARED_SECRET="strong-secret-prod-12345",
                ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION=True,
            )

    def test_production_rejects_default_webhook_secret(self) -> None:
        with pytest.raises(ValidationError, match="Default insecure WEBHOOK_SHARED_SECRET"):
            Settings(
                APP_ENV="production",
                DEBUG=False,
                CHECKPOINTER_BACKEND="postgres",
                WEBHOOK_SHARED_SECRET="fieldops-webhook-secret-dev",
                ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION=True,
            )

    def test_production_rejects_sqlite_checkpointer(self) -> None:
        with pytest.raises(ValidationError, match="Local SQLite checkpointer is not allowed in production"):
            Settings(
                APP_ENV="production",
                DEBUG=False,
                CHECKPOINTER_BACKEND="sqlite",
                WEBHOOK_SHARED_SECRET="strong-secret-prod-12345",
                ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION=True,
            )

    def test_production_rejects_fake_integrations_without_explicit_override(self) -> None:
        with pytest.raises(ValidationError, match="Fake integration providers are not allowed in production"):
            Settings(
                APP_ENV="production",
                DEBUG=False,
                CHECKPOINTER_BACKEND="postgres",
                WEBHOOK_SHARED_SECRET="strong-secret-prod-12345",
                ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION=False,
            )

    def test_production_accepts_valid_configuration(self) -> None:
        s = Settings(
            APP_ENV="production",
            DEBUG=False,
            CHECKPOINTER_BACKEND="postgres",
            WEBHOOK_SHARED_SECRET="strong-secret-prod-12345",
            ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION=True,
        )
        assert s.APP_ENV == "production"
        assert s.CHECKPOINTER_BACKEND == "postgres"
        assert s.DEBUG is False
        assert s.ENABLE_FAKE_INTAKE is False


class TestCheckpointerUpgrade:
    """Verify checkpointer backend routing and stateless API support."""

    def setup_method(self) -> None:
        reset_checkpointer()

    def teardown_method(self) -> None:
        reset_checkpointer()

    def test_sqlite_checkpointer_instantiation(self) -> None:
        saver = get_checkpointer(db_path=":memory:")
        from langgraph.checkpoint.sqlite import SqliteSaver
        assert isinstance(saver, SqliteSaver)

    def test_postgres_checkpointer_instantiation(self) -> None:
        with patch("psycopg_pool.ConnectionPool") as mock_pool_cls, \
             patch("langgraph.checkpoint.postgres.PostgresSaver") as mock_saver_cls:
            mock_pool = MagicMock()
            mock_pool_cls.return_value = mock_pool
            mock_saver = MagicMock()
            mock_saver_cls.return_value = mock_saver

            saver = get_checkpointer(backend="postgres")
            assert saver == mock_saver
            mock_saver.setup.assert_called_once()
            mock_pool_cls.assert_called_once()


class TestHealthAndReadinessProbes:
    """Verify separate liveness and readiness probe semantics."""

    def test_health_liveness_probe_returns_200(self) -> None:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    def test_readiness_probe_returns_200_when_all_healthy(self) -> None:
        with patch("redis.from_url") as mock_redis_cls:
            mock_redis = MagicMock()
            mock_redis.ping.return_value = True
            mock_redis_cls.return_value = mock_redis

            res = client.get("/ready")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert data["database"] == "ok"
            assert data["redis"] == "ok"

    def test_readiness_probe_returns_degraded_when_redis_fails(self) -> None:
        with patch("redis.from_url") as mock_redis_cls:
            mock_redis = MagicMock()
            mock_redis.ping.side_effect = Exception("Redis connection refused")
            mock_redis_cls.return_value = mock_redis

            res = client.get("/ready")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "degraded"
            assert data["database"] == "ok"
            assert data["redis"] == "degraded"

    def test_readiness_probe_returns_503_when_database_fails(self) -> None:
        with patch("fieldops.main.SessionLocal") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.execute.side_effect = Exception("DB connection timeout")
            mock_session_cls.return_value.__enter__.return_value = mock_session

            res = client.get("/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "error"


class TestCorsMiddleware:
    """Verify CORS headers are emitted for client requests."""

    def test_cors_preflight_response(self) -> None:
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Idempotency-Key",
        }
        res = client.options("/service-requests", headers=headers)
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
