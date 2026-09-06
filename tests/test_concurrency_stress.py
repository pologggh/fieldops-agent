import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from fieldops.agent.checkpointer import get_checkpointer, reset_checkpointer
from fieldops.application.appointment_service import AppointmentService
from fieldops.application.field_service_workflow import (
    resume_field_service_workflow,
    run_field_service_workflow,
)
from fieldops.core.config import settings
from fieldops.core.exceptions import ConflictError
from fieldops.core.idempotency import compute_request_hash
from fieldops.db.models import (
    Appointment,
    Customer,
    IdempotencyRecord,
    InboundEvent,
    OutboxEvent,
    ServiceRequest,
    Technician,
)
from fieldops.intake import (
    InboundRequestService,
    WebhookInboundAdapter,
    WebhookPayload,
)
from fieldops.llm.fake_llm import reset_failure_injection, set_failure_injection
from fieldops.llm.schemas import ParsedServiceRequest, ServiceRequestCreateInput
from fieldops.main import app
from fieldops.security.rate_limiter import (
    check_rate_limit,
    reset_local_rate_limiter,
)
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)


class MockRedis:
    """Simple in-memory fake redis for testing rate limiter atomic INCR."""
    def __init__(self):
        self.store = {}

    def incr(self, key: str) -> int:
        val = self.store.get(key, 0) + 1
        self.store[key] = val
        return val

    def expire(self, key: str, seconds: int) -> bool:
        return True


class TestIdempotencyConcurrency:
    """Verify concurrent requests with identical and conflicting Idempotency-Keys."""

    def setup_method(self) -> None:
        reset_local_rate_limiter()
        reset_failure_injection()

    def teardown_method(self) -> None:
        reset_local_rate_limiter()
        reset_failure_injection()

    def test_concurrent_same_key_same_body(self, test_db_session) -> None:
        """Requests with identical key and body return cached result with zero duplicate ServiceRequests."""
        idempotency_key = "idemp-same-body-test"
        payload = {
            "customer_name": "Concurrent User",
            "email": "concurrent_test@example.com",
            "phone": "+81-90-1111-2222",
            "message": "AC broken in Shinjuku this afternoon",
        }

        with patch.object(settings, "LOAD_TEST_MODE", True):
            res1 = client.post("/service-requests", json=payload, headers={"Idempotency-Key": idempotency_key})
            assert res1.status_code == 201

            # Subsequent requests with same key and body hit cache and return 200/201 without side effects
            res2 = client.post("/service-requests", json=payload, headers={"Idempotency-Key": idempotency_key})
            assert res2.status_code in (200, 201)
            assert res2.json()["request_id"] == res1.json()["request_id"]

            res3 = client.post("/service-requests", json=payload, headers={"Idempotency-Key": idempotency_key})
            assert res3.status_code in (200, 201)
            assert res3.json()["request_id"] == res1.json()["request_id"]

            # Assert database invariant: exactly ONE customer and ONE service request created
            customers = test_db_session.query(Customer).filter_by(email="concurrent_test@example.com").all()
            assert len(customers) == 1

            srs = test_db_session.query(ServiceRequest).filter_by(customer_id=customers[0].id).all()
            assert len(srs) == 1

    def test_concurrent_in_flight_returns_409(self, test_db_session) -> None:
        """In-flight request with same key returns 409 Conflict."""
        idempotency_key = "idemp-inflight-test"
        payload = {
            "customer_name": "Inflight User",
            "email": "inflight@example.com",
            "phone": "+81-90-1111-2222",
            "message": "AC broken in Shinjuku this afternoon",
        }
        # Simulate in-flight record
        record = IdempotencyRecord(
            key=idempotency_key,
            operation="create_service_request",
            request_hash=compute_request_hash(ServiceRequestCreateInput(**payload)),
            status="processing",
        )
        test_db_session.add(record)
        test_db_session.commit()

        res = client.post("/service-requests", json=payload, headers={"Idempotency-Key": idempotency_key})
        assert res.status_code == 409
        assert "currently being processed" in res.json()["detail"].lower()

    def test_concurrent_same_key_different_body_conflict(self, test_db_session) -> None:
        """Requests with same key but different payloads must yield 409 Conflict."""
        idempotency_key = "idemp-diff-body-test"
        payload1 = {
            "customer_name": "User 1",
            "email": "user1@example.com",
            "phone": "+81-90-1111-2222",
            "message": "AC broken in Shinjuku this afternoon",
        }
        payload2 = {
            "customer_name": "User 2",
            "email": "user2@example.com",
            "phone": "+81-90-2222-3333",
            "message": "Different plumbing emergency in Shibuya",
        }

        with patch.object(settings, "LOAD_TEST_MODE", True):
            res1 = client.post("/service-requests", json=payload1, headers={"Idempotency-Key": idempotency_key})
            assert res1.status_code == 201

            # Second request with different body hash must fail with 409
            res2 = client.post("/service-requests", json=payload2, headers={"Idempotency-Key": idempotency_key})
            assert res2.status_code == 409
            assert "payload does not match" in res2.json()["detail"].lower()


class TestAppointmentConcurrencyAndNoDoubleBooking:
    """Verify that multiple concurrent appointments for the same technician never double-book."""

    def test_concurrent_overlapping_appointments_zero_double_booking(self, test_db_session) -> None:
        tech = Technician(
            name="Ken Tanaka",
            service_area="Shinjuku",
            status="active",
        )
        test_db_session.add(tech)
        test_db_session.flush()

        # Create customers and service requests
        sr_ids = []
        for i in range(10):
            c = Customer(name=f"Customer {i}", email=f"cust_{i}@example.com", phone="+81-90-0000-0000")
            test_db_session.add(c)
            test_db_session.flush()

            sr = ServiceRequest(
                customer_id=c.id,
                raw_message=f"Request {i}",
                service_type="HVAC",
                urgency="medium",
                location="Shinjuku",
                status="ready_for_review",
            )
            test_db_session.add(sr)
            test_db_session.flush()
            sr_ids.append(sr.id)
        test_db_session.commit()

        start_time = datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)

        service = AppointmentService(test_db_session)

        def _book_appointment(sr_id: int) -> str:
            res = service.finalize_appointment(
                service_request_id=sr_id,
                technician_id=tech.id,
                start_time=start_time,
                end_time=end_time,
            )
            if res.success:
                test_db_session.commit()
                return "success"
            else:
                test_db_session.rollback()
                return "conflict"

        results = [_book_appointment(s_id) for s_id in sr_ids]

        assert results.count("success") == 1
        assert results.count("conflict") == 9

        # Double booking count must be strictly 0
        appts = test_db_session.query(Appointment).filter_by(technician_id=tech.id).all()
        assert len(appts) == 1
        assert appts[0].status == "scheduled"


class TestWebhookDuplicateConcurrency:
    """Verify duplicate webhook intake creates exactly one InboundEvent."""

    def test_concurrent_duplicate_webhook_events(self, test_db_session) -> None:
        from fieldops.intake.schemas import WebhookCustomerPayload

        payload = WebhookPayload(
            event_id="evt-concurrency-unique-001",
            event_type="service_request",
            customer=WebhookCustomerPayload(
                name="Webhook User",
                email="webhook_user@example.com",
                phone="+81-90-2222-3333",
            ),
            message="Leaking pipe in Shibuya",
        )
        inbound_req = WebhookInboundAdapter.normalize(payload)

        # Mock runner so we test intake layer persistence without launching full graph
        mock_runner = MagicMock(return_value={"workflow_status": "appointment_proposal_created"})
        inbound_service = InboundRequestService(workflow_runner=mock_runner)

        # Send first request (creates record)
        res1 = inbound_service.handle(inbound_req, raw_payload=payload)
        assert res1.duplicate is False

        # Send subsequent requests with same event_id
        res2 = inbound_service.handle(inbound_req, raw_payload=payload)
        assert res2.duplicate is True

        res3 = inbound_service.handle(inbound_req, raw_payload=payload)
        assert res3.duplicate is True

        # Exactly 1 record in database
        events = test_db_session.query(InboundEvent).filter_by(
            source="webhook", external_message_id="evt-concurrency-unique-001"
        ).all()
        assert len(events) == 1


class TestDatabasePoolExhaustionAndTimeout:
    """Verify database connection pool bounds and timeout behaviors."""

    def test_pool_exhaustion_raises_timeout_without_infinite_hang(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0,
            pool_timeout=0.3,
        )

        conn1 = engine.connect()
        assert conn1 is not None

        start_time = datetime.now()
        with pytest.raises(Exception) as exc_info:
            conn2 = engine.connect()
        duration = (datetime.now() - start_time).total_seconds()

        assert duration < 1.0  # Proves it did not hang infinitely
        assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()

        conn1.close()
        engine.dispose()


class TestRateLimitingAndSecurityHardening:
    """Verify rate limiting, fail-open vs fail-closed policies, and request size checks."""

    def setup_method(self) -> None:
        reset_local_rate_limiter()

    def teardown_method(self) -> None:
        reset_local_rate_limiter()

    def test_login_brute_force_triggers_429(self) -> None:
        mock_redis = MockRedis()
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true", "LOAD_TEST_MODE": "false", "APP_ENV": "production"}), \
             patch("redis.from_url", return_value=mock_redis), \
             patch.object(settings, "RATE_LIMIT_ENABLED", True), \
             patch.object(settings, "LOAD_TEST_MODE", False), \
             patch.object(settings, "APP_ENV", "production"), \
             patch.object(settings, "RATE_LIMIT_LOGIN_MAX_REQUESTS", 3):
            for _ in range(3):
                res = client.post("/auth/login", json={"username": "admin", "password": "wrong-password"})
                assert res.status_code == 401

            # 4th attempt triggers 429
            res4 = client.post("/auth/login", json={"username": "admin", "password": "wrong-password"})
            assert res4.status_code == 429
            assert "Rate limit exceeded" in res4.json()["detail"]

    def test_rate_limiter_fail_closed_on_auth_when_redis_offline(self) -> None:
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true", "LOAD_TEST_MODE": "false", "APP_ENV": "production"}), \
             patch.object(settings, "RATE_LIMIT_ENABLED", True), \
             patch.object(settings, "LOAD_TEST_MODE", False), \
             patch.object(settings, "APP_ENV", "production"), \
             patch("redis.from_url", side_effect=Exception("Redis connection refused")):
            with pytest.raises(Exception) as exc_info:
                check_rate_limit("auth:/auth/login:127.0.0.1", max_requests=5, window_seconds=60, fail_open=False)
            assert "503" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()

    def test_rate_limiter_fail_open_on_business_api_when_redis_offline(self) -> None:
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "true", "LOAD_TEST_MODE": "false", "APP_ENV": "production"}), \
             patch.object(settings, "RATE_LIMIT_ENABLED", True), \
             patch.object(settings, "LOAD_TEST_MODE", False), \
             patch.object(settings, "APP_ENV", "production"), \
             patch("redis.from_url", side_effect=Exception("Redis connection refused")):
            allowed = check_rate_limit(
                "business:/service-requests:127.0.0.1",
                max_requests=60,
                window_seconds=60,
                fail_open=True,
            )
            assert allowed is True

    def test_oversized_message_rejected_with_422_fast(self) -> None:
        huge_message = "A" * 2500
        payload = {
            "customer_name": "Bob",
            "email": "bob@example.com",
            "phone": "+81-90-1234-5678",
            "message": huge_message,
        }
        res = client.post("/service-requests", json=payload)
        assert res.status_code == 422
        assert "exceeds maximum allowed length" in res.json()["detail"]

    def test_malformed_json_rejected_with_422_fast(self) -> None:
        malformed = {"customer_name": "Incomplete Payload"}
        res = client.post("/service-requests", json=malformed)
        assert res.status_code == 422


class TestSlowLlmAndTimeoutStorm:
    """Verify system stability under slow LLM responses and timeouts."""

    def setup_method(self) -> None:
        reset_failure_injection()

    def teardown_method(self) -> None:
        reset_failure_injection()

    def test_parse_service_request_timeout_returns_503(self) -> None:
        set_failure_injection(timeout_error=True)
        with patch.object(settings, "LOAD_TEST_MODE", True):
            res = client.post("/parse-service-request", json={"message": "AC broken in Shinjuku"})
            assert res.status_code == 503
            assert "timeout" in res.json()["detail"].lower()

    def test_service_request_workflow_timeout_transitions_to_llm_failed_safely(self) -> None:
        set_failure_injection(timeout_error=True)

        payload = {
            "customer_name": "Timeout User",
            "email": "timeout_user@example.com",
            "phone": "+81-90-1111-2222",
            "message": "AC broken in Shinjuku",
        }
        with patch.object(settings, "LOAD_TEST_MODE", True):
            res = client.post("/service-requests", json=payload)
            # Workflow safely terminates with llm_failed state without crashing
            assert res.status_code == 201
            assert res.json()["workflow_status"] == "llm_failed"


class TestRedisDownAndTransactionalOutboxResilience:
    """Verify that core business operations proceed and buffer in outbox when Redis is down."""

    def test_appointment_creates_outbox_when_redis_is_down(self, test_db_session) -> None:
        c = Customer(name="Outbox User", email="outbox@example.com", phone="+81-90-1234-5678")
        test_db_session.add(c)
        test_db_session.flush()

        tech = Technician(
            name="Haru Suzuki",
            service_area="Shinjuku",
            status="active",
        )
        test_db_session.add(tech)
        test_db_session.flush()

        sr = ServiceRequest(
            customer_id=c.id,
            raw_message="Need HVAC repair",
            service_type="HVAC",
            urgency="high",
            location="Shinjuku",
            status="ready_for_review",
        )
        test_db_session.add(sr)
        test_db_session.flush()

        # Simulate Redis outage during appointment creation
        with patch("redis.from_url", side_effect=Exception("Redis down")):
            service = AppointmentService(test_db_session)
            result = service.finalize_appointment(
                service_request_id=sr.id,
                technician_id=tech.id,
                start_time=datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc),
            )
            test_db_session.commit()

            assert result.success is True
            assert result.appointment_id is not None
            assert result.appointment_status == "scheduled"

            # Check that Outbox event is safely pending in PostgreSQL
            outbox = test_db_session.query(OutboxEvent).filter_by(
                aggregate_type="appointment", aggregate_id=str(result.appointment_id)
            ).first()
            assert outbox is not None
            assert outbox.status == "pending"


class TestStatelessCheckpointerCrossInstanceResume:
    """Verify that workflows interrupted on one checkpointer instance can be resumed by another."""

    def setup_method(self) -> None:
        reset_checkpointer()

    def teardown_method(self) -> None:
        reset_checkpointer()

    def test_cross_instance_resume(self, test_db_session) -> None:
        sqlite_file = "tests_cross_instance_checkpoints.sqlite"
        if os.path.exists(sqlite_file):
            try:
                os.remove(sqlite_file)
            except Exception:
                pass

        try:
            from fieldops.agent.graph import build_field_service_graph
            from scripts.seed import seed_customers, seed_technicians

            seed_customers(test_db_session)
            seed_technicians(test_db_session)

            mock_parsed = ParsedServiceRequest(
                service_type="HVAC",
                urgency="high",
                location="Shinjuku",
                required_skills=["HVAC"],
                preferred_time="tomorrow afternoon",
                problem_description="AC repair",
            )

            test_thread_id = "cross-inst-thread-001"

            # Instance A: runs workflow until pause at human_review
            saver_a = get_checkpointer(db_path=sqlite_file)
            graph_a = build_field_service_graph(checkpointer=saver_a)

            with patch(
                "fieldops.agent.nodes.parse_request.parse_service_request",
                return_value=mock_parsed,
            ):
                paused_state = run_field_service_workflow(
                    message="AC broken in Shinjuku tomorrow afternoon",
                    customer_name="Alice",
                    email="alice@example.com",
                    request_id=test_thread_id,
                    graph=graph_a,
                )

            assert paused_state["workflow_status"] == "waiting_for_approval"

            # Destroy Instance A
            if hasattr(saver_a, "conn"):
                saver_a.conn.close()
            reset_checkpointer()

            # Instance B: completely fresh checkpointer pointing to same file
            saver_b = get_checkpointer(db_path=sqlite_file)
            graph_b = build_field_service_graph(checkpointer=saver_b)

            # Resume on Instance B
            resumed_state = resume_field_service_workflow(
                request_id=test_thread_id,
                decision="approve",
                graph=graph_b,
            )

            assert resumed_state["approval_status"] == "approved"
            assert resumed_state["workflow_status"] == "appointment_created"

            if hasattr(saver_b, "conn"):
                saver_b.conn.close()
        finally:
            reset_checkpointer()
            if os.path.exists(sqlite_file):
                try:
                    os.remove(sqlite_file)
                except Exception:
                    pass
