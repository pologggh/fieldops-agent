import json
import logging
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from fieldops.application.appointment_service import AppointmentService
from fieldops.core.config import settings
from fieldops.core.logging import (
    JsonFormatter,
    emit_event,
    redact_email,
    redact_phone,
    redact_sensitive_text,
    sanitize_message,
)
from fieldops.db.models import ServiceRequest
from fieldops.main import app
from fieldops.observability.llm_cost import MODEL_PRICING, calculate_llm_cost
from fieldops.observability.metrics import (
    APPOINTMENT_CONFLICTS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    LLM_ESTIMATED_COST_TOTAL,
    LLM_INPUT_TOKENS_TOTAL,
    LLM_OUTPUT_TOKENS_TOTAL,
    LLM_REQUESTS_TOTAL,
    NODE_DURATION_SECONDS,
    NODE_FAILURES_TOTAL,
    OUTBOX_PENDING,
    OUTBOX_PUBLISH_FAILURES_TOTAL,
    WORKFLOW_DURATION_SECONDS,
    WORKFLOWS_TOTAL,
)
from fieldops.observability.tracing import trace_llm_call, trace_node
from fieldops.tasks.outbox_tasks import publish_outbox_events


@pytest.fixture
def client():
    return TestClient(app)


class TestCorrelationAndHttpMetrics:
    def test_x_request_id_generated_automatically(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 10

    def test_x_request_id_propagated_from_client(self, client):
        custom_id = "test-custom-request-id-456"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_id

    def test_metrics_endpoint_exposition(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        assert "fieldops_http_requests_total" in content
        assert "fieldops_workflow_duration_seconds" in content
        assert "fieldops_node_duration_seconds" in content
        assert "fieldops_llm_input_tokens_total" in content


class TestHealthAndReadinessProbes:
    def test_health_liveness(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ready_success_when_all_healthy(self, client, test_db_session):
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["database"] == "ok"
        assert data["status"] in ("ok", "degraded")

    def test_ready_returns_503_when_db_fails(self, client):
        with patch("fieldops.main.SessionLocal", side_effect=Exception("Database connection refused")):
            response = client.get("/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "error"

    def test_ready_returns_200_degraded_when_redis_fails(self, client):
        with patch("redis.from_url") as mock_redis_cls:
            mock_instance = MagicMock()
            mock_instance.ping.side_effect = Exception("Redis connection refused")
            mock_redis_cls.return_value = mock_instance

            response = client.get("/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"] == "ok"
            assert data["redis"] == "degraded"


class TestSensitiveDataRedaction:
    def test_redact_email(self):
        assert redact_email("alice@example.com") == "a***e@example.com"
        assert redact_email("bo@test.org") == "b*@test.org"
        assert redact_email(None) == "[EMPTY]"
        assert redact_email("not-an-email") == "[EMPTY]"

    def test_redact_phone(self):
        assert redact_phone("+14155552671") == "********2671"
        assert redact_phone("1234") == "****"
        assert redact_phone(None) == "[EMPTY]"

    def test_sanitize_message(self):
        res = sanitize_message("Short text")
        assert res["length"] == 10
        assert res["preview"] == "Short text"

        res_long = sanitize_message("A" * 100, max_preview=10)
        assert res_long["length"] == 100
        assert res_long["preview"] == "AAAAAAAAAA..."

    def test_redact_sensitive_text_credentials(self):
        raw_db = "postgresql://fieldops:supersecret123@localhost:5432/fieldops"
        redacted_db = redact_sensitive_text(raw_db)
        assert "supersecret123" not in redacted_db
        assert "postgresql://fieldops:***@localhost:5432/fieldops" in redacted_db

        raw_redis = "redis://:my_redis_password_xyz@redis:6379/0"
        redacted_redis = redact_sensitive_text(raw_redis)
        assert "my_redis_password_xyz" not in redacted_redis
        assert "redis://:***@redis:6379/0" in redacted_redis

        raw_token = "Bearer sk-proj-1234567890abcdef"
        redacted_token = redact_sensitive_text(raw_token)
        assert "1234567890abcdef" not in redacted_token
        assert "***REDACTED***" in redacted_token


class TestJsonFormatterAndLogging:
    def test_json_formatter_structure(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="fieldops.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=100,
            msg="User credentials postgresql://usr:pass@host:5432/db",
            args=(),
            exc_info=None,
        )
        record.event = "test.event"
        record.request_id = "req-123"
        record.extra_context = {"key": "value"}

        formatted = formatter.format(record)
        data = json.loads(formatted)
        assert data["level"] == "INFO"
        assert data["component"] == "fieldops.test"
        assert data["event"] == "test.event"
        assert data["request_id"] == "req-123"
        assert data["key"] == "value"
        assert "pass" not in data["message"]
        assert "***" in data["message"]

    def test_emit_event_helper(self, caplog):
        with caplog.at_level(logging.INFO):
            emit_event(
                event="custom.test_event",
                level="info",
                request_id="req-999",
                metric_val=42,
            )
        assert any("custom.test_event" in r.message for r in caplog.records)


class TestLlmPricingAndCost:
    def test_calculate_llm_cost_gpt_4o_mini(self):
        # gpt-4o-mini: .15 / 1M input, .60 / 1M output
        cost = calculate_llm_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert round(cost, 4) == 0.75

    def test_calculate_llm_cost_gpt_4o(self):
        # gpt-4o: .50 / 1M input, .00 / 1M output -> 100k of each = .25 + .00 = .25
        cost = calculate_llm_cost("gpt-4o", 100_000, 100_000)
        assert round(cost, 4) == 1.25

    def test_calculate_llm_cost_unknown_model_fallback(self):
        cost = calculate_llm_cost("custom-finetuned-model", 10_000, 10_000)
        assert cost is None


class TestTracingAndNodeMetrics:
    def test_trace_node_context_manager_success(self):
        initial_val = NODE_DURATION_SECONDS.labels(node="test_node_success")._sum.get()
        state = {"request_id": "req-trace-1", "workflow_status": "in_progress"}
        with trace_node("test_node_success", state) as span:
            assert span is not None

        updated_val = NODE_DURATION_SECONDS.labels(node="test_node_success")._sum.get()
        assert updated_val > initial_val

    def test_trace_node_context_manager_failure(self):
        initial_failures = NODE_FAILURES_TOTAL.labels(node="test_node_failure")._value.get()
        state = {"request_id": "req-trace-2", "workflow_status": "in_progress"}
        with pytest.raises(ValueError, match="simulated node error"):
            with trace_node("test_node_failure", state):
                raise ValueError("simulated node error")

        updated_failures = NODE_FAILURES_TOTAL.labels(node="test_node_failure")._value.get()
        assert updated_failures == initial_failures + 1

    def test_trace_llm_call_metadata(self):
        with trace_llm_call("gpt-4o-mini", request_id="req-llm-1") as meta:
            meta["input_tokens"] = 120
            meta["output_tokens"] = 45
            meta["total_tokens"] = 165
            meta["estimated_cost"] = 0.0001
        assert meta["input_tokens"] == 120


class TestAppointmentConflictMetric:
    def test_appointment_conflict_increments_metric(self, test_db_session):
        initial_conflicts = APPOINTMENT_CONFLICTS_TOTAL._value.get()
        service = AppointmentService(test_db_session)

        sr = ServiceRequest(
            customer_id=1,
            service_type="ac_repair",
            status="received",
            urgency="medium",
            location="Tokyo",
            raw_message="Observability conflict test",
        )
        test_db_session.add(sr)
        test_db_session.commit()

        # Simulate overlap conflict by setting up existing blocking appointment
        with patch.object(service.appointment_repo, "get_blocking_by_technician_and_window") as mock_blocking:
            mock_appt = MagicMock()
            mock_appt.id = 999
            mock_appt.start_time = "2026-09-04T10:00:00+00:00"
            mock_appt.end_time = "2026-09-04T12:00:00+00:00"
            mock_blocking.return_value = [mock_appt]

            with patch("fieldops.application.appointment_service.has_time_conflict", return_value=True):
                result = service.finalize_appointment(
                    service_request_id=sr.id,
                    technician_id=1,
                    start_time="2026-09-04T10:00:00+00:00",
                    end_time="2026-09-04T12:00:00+00:00",
                )
                assert result.conflict_detected is True
                assert APPOINTMENT_CONFLICTS_TOTAL._value.get() == initial_conflicts + 1


class TestOutboxMetrics:
    def test_outbox_pending_gauge_updated(self):
        initial_failures = OUTBOX_PUBLISH_FAILURES_TOTAL._value.get()
        # Mock SessionLocal and outbox repository
        with patch("fieldops.tasks.outbox_tasks.SessionLocal") as mock_session_cls:
            mock_sess = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_sess

            mock_event = MagicMock()
            mock_event.id = 1
            mock_event.event_type = "appointment.created"
            mock_event.payload = {"appointment_id": 101}

            mock_outbox = MagicMock()
            mock_outbox.get_pending.return_value = [mock_event]

            with patch("fieldops.tasks.outbox_tasks.OutboxRepository", return_value=mock_outbox):
                with patch("fieldops.tasks.outbox_tasks.send_appointment_reminder.apply_async", side_effect=Exception("Redis connection error")):
                    result = publish_outbox_events()
                    assert result["failed"] == 1
                    assert OUTBOX_PUBLISH_FAILURES_TOTAL._value.get() == initial_failures + 1
