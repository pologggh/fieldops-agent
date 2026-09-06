"""Unit and integration tests for Phase 16: Inbound Request Intake Architecture."""

from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.core.config import settings
from fieldops.core.exceptions import ValidationError
from fieldops.llm.exceptions import LLMCallError
from fieldops.db.models import Customer, InboundEvent, ServiceRequest
from fieldops.intake import (
    FakeEmailInboundAdapter,
    FakeEmailPayload,
    InboundRequestService,
    InboundServiceRequest,
    InboundSource,
    WebInboundAdapter,
    WebhookCustomerPayload,
    WebhookInboundAdapter,
    WebhookPayload,
)
from fieldops.llm.schemas import ParsedServiceRequest, ServiceRequestCreateInput
from fieldops.main import app
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.inbound_event_repository import InboundEventRepository
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)

MOCK_PARSED_HVAC = ParsedServiceRequest(
    service_type="HVAC",
    urgency="high",
    location="Shinjuku",
    required_skills=["HVAC"],
    preferred_time="tomorrow afternoon",
    problem_description="AC smells like burning",
)


# ==============================================================================
# 1. Adapter Unit Tests
# ==============================================================================


class TestInboundAdapters:
    def test_web_adapter_normalization(self):
        payload = ServiceRequestCreateInput(
            customer_name="  Bob Builder ",
            email="bob@example.com",
            phone="090-1234-5678",
            message="Water pipe leak in kitchen",
        )
        normalized = WebInboundAdapter.normalize(payload)

        assert normalized.source == InboundSource.WEB
        assert normalized.external_message_id is None
        assert normalized.customer_name == "Bob Builder"
        assert normalized.customer_email == "bob@example.com"
        assert normalized.customer_phone == "090-1234-5678"
        assert normalized.message == "Water pipe leak in kitchen"
        assert normalized.metadata["channel"] == "web_form"

    def test_fake_email_adapter_normalization_with_subject(self):
        payload = FakeEmailPayload(
            message_id="msg-1001",
            from_name="Alice Wonder",
            from_email="alice@example.com",
            subject="AC Urgent Issue",
            body="My AC stopped working and smells like burning.",
        )
        normalized = FakeEmailInboundAdapter.normalize(payload)

        assert normalized.source == InboundSource.FAKE_EMAIL
        assert normalized.external_message_id == "msg-1001"
        assert normalized.customer_name == "Alice Wonder"
        assert normalized.customer_email == "alice@example.com"
        assert normalized.customer_phone is None
        assert normalized.message == "AC Urgent Issue\n\nMy AC stopped working and smells like burning."
        assert normalized.metadata["original_message_id"] == "msg-1001"

    def test_fake_email_adapter_normalization_without_subject(self):
        payload = FakeEmailPayload(
            message_id="msg-1002",
            from_name="Charlie",
            from_email="charlie@example.com",
            subject="",
            body="Plumbing problem in Shibuya.",
        )
        normalized = FakeEmailInboundAdapter.normalize(payload)
        assert normalized.message == "Plumbing problem in Shibuya."

    def test_webhook_adapter_normalization_success(self):
        payload = WebhookPayload(
            event_id="evt-999",
            event_type="service_request",
            customer=WebhookCustomerPayload(
                name="Dave",
                email="dave@example.com",
                phone="080-9999-8888",
            ),
            message="Server room AC failure",
        )
        normalized = WebhookInboundAdapter.normalize(payload)

        assert normalized.source == InboundSource.WEBHOOK
        assert normalized.external_message_id == "evt-999"
        assert normalized.customer_name == "Dave"
        assert normalized.customer_email == "dave@example.com"
        assert normalized.customer_phone == "080-9999-8888"
        assert normalized.message == "Server room AC failure"
        assert normalized.metadata["event_type"] == "service_request"

    def test_webhook_adapter_unsupported_event_type_raises(self):
        payload = WebhookPayload(
            event_id="evt-1000",
            event_type="payment_completed",
            customer=WebhookCustomerPayload(name="Eve"),
            message="Payment received",
        )
        with pytest.raises(ValidationError) as exc:
            WebhookInboundAdapter.normalize(payload)
        assert "Unsupported webhook event_type" in str(exc.value)


# ==============================================================================
# 2. Web API Regression Tests (POST /service-requests)
# ==============================================================================


class TestWebIntakeRegression:
    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_web_service_request_creates_records_and_inbound_event(
        self, mock_parse, test_db_session: Session
    ):
        res = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice Web",
                "email": "alice.web@example.com",
                "phone": "090-0000-1111",
                "message": "AC smells like burning in Shinjuku.",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert "request_id" in data
        assert data["service_request_id"] is not None
        assert data["service_type"] == "HVAC"

        # Check database records
        event_repo = InboundEventRepository(test_db_session)
        events = test_db_session.execute(
            select(InboundEvent).where(InboundEvent.source == "web")
        ).scalars().all()
        assert len(events) >= 1
        assert events[-1].status == "completed"
        assert events[-1].service_request_id == data["service_request_id"]

    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_web_idempotency_key_cached_response(
        self, mock_parse, test_db_session: Session
    ):
        headers = {"Idempotency-Key": "web-idem-key-100"}
        body = {
            "customer_name": "Bob Web",
            "email": "bob.web@example.com",
            "phone": "090-2222-3333",
            "message": "Kitchen water leak",
        }

        # First request
        res1 = client.post("/service-requests", json=body, headers=headers)
        assert res1.status_code == 201
        sr_id1 = res1.json()["service_request_id"]

        # Duplicate request with same key and body -> cached response
        res2 = client.post("/service-requests", json=body, headers=headers)
        assert res2.status_code == 201
        assert res2.json()["service_request_id"] == sr_id1

        # Same key with different payload -> 409 Conflict
        res3 = client.post(
            "/service-requests",
            json={**body, "message": "Different issue text"},
            headers=headers,
        )
        assert res3.status_code == 409


# ==============================================================================
# 3. Fake Email Intake Tests (POST /intake/fake-email)
# ==============================================================================


class TestFakeEmailIntake:
    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_fake_email_intake_success(
        self, mock_parse, test_db_session: Session
    ):
        email_payload = {
            "message_id": "fake-mail-001",
            "from_name": "Alice Email",
            "from_email": "alice.email@example.com",
            "subject": "Burning Smell from AC",
            "body": "My AC stopped working and smells like burning. I am in Shinjuku.",
        }

        res = client.post("/intake/fake-email", json=email_payload)
        assert res.status_code == 201
        data = res.json()

        assert data["source"] == "fake_email"
        assert data["duplicate"] is False
        assert data["service_request_id"] is not None
        assert data["workflow_status"] in ("ready_for_scheduling", "no_technician_available")

        # Verify InboundEvent in database
        event_repo = InboundEventRepository(test_db_session)
        event = event_repo.get_by_source_and_external_id("fake_email", "fake-mail-001")
        assert event is not None
        assert event.status == "completed"
        assert event.service_request_id == data["service_request_id"]

    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_fake_email_duplicate_idempotency(
        self, mock_parse, test_db_session: Session
    ):
        email_payload = {
            "message_id": "fake-mail-dup-002",
            "from_name": "Charlie Email",
            "from_email": "charlie.email@example.com",
            "subject": "Filter replacement",
            "body": "Need filter replacement in Shinjuku.",
        }

        # First delivery
        res1 = client.post("/intake/fake-email", json=email_payload)
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["duplicate"] is False
        sr_id = data1["service_request_id"]

        # Duplicate delivery with same message_id and body
        res2 = client.post("/intake/fake-email", json=email_payload)
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["duplicate"] is True
        assert data2["service_request_id"] == sr_id

        # Database must only have 1 ServiceRequest and 1 InboundEvent
        sr_count = len(
            test_db_session.execute(
                select(ServiceRequest).where(ServiceRequest.customer_id.in_(
                    select(Customer.id).where(Customer.email == "charlie.email@example.com")
                ))
            ).scalars().all()
        )
        assert sr_count == 1

        # AuditLog should contain inbound.duplicate
        event = InboundEventRepository(test_db_session).get_by_source_and_external_id("fake_email", "fake-mail-dup-002")
        assert event is not None
        audit_repo = AuditLogRepository(test_db_session)
        logs = audit_repo.list_by_entity("inbound_event", str(event.id))
        dup_logs = [log for log in logs if log.action == "inbound.duplicate"]
        assert len(dup_logs) == 1

    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_fake_email_same_id_different_payload_conflicts(
        self, mock_parse, test_db_session: Session
    ):
        email_payload_1 = {
            "message_id": "fake-mail-conflict-003",
            "from_name": "Dave",
            "from_email": "dave@example.com",
            "subject": "Initial subject",
            "body": "Initial body message.",
        }
        res1 = client.post("/intake/fake-email", json=email_payload_1)
        assert res1.status_code == 201

        # Same message_id with modified payload -> 409 Conflict
        email_payload_2 = {
            **email_payload_1,
            "body": "Modified body content with completely different text.",
        }
        res2 = client.post("/intake/fake-email", json=email_payload_2)
        assert res2.status_code == 409
        assert "Inbound conflict" in res2.json()["detail"]

    def test_fake_email_production_guard_disabled(self):
        with patch.object(settings, "APP_ENV", "production"), \
             patch.object(settings, "ENABLE_FAKE_INTAKE", False):
            res = client.post(
                "/intake/fake-email",
                json={
                    "message_id": "fake-mail-prod",
                    "from_name": "Test",
                    "from_email": "test@example.com",
                    "subject": "Test",
                    "body": "Test",
                },
            )
            assert res.status_code == 403
            assert "Fake email intake is disabled in production" in res.json()["detail"]


# ==============================================================================
# 4. Webhook Intake Tests (POST /intake/webhook)
# ==============================================================================


class TestWebhookIntake:
    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_webhook_intake_success_with_valid_secret(
        self, mock_parse, test_db_session: Session
    ):
        payload = {
            "event_id": "hook-evt-001",
            "event_type": "service_request",
            "customer": {
                "name": "Webhook Alice",
                "email": "wh.alice@example.com",
                "phone": "03-1234-5678",
            },
            "message": "AC is freezing up and shutting down.",
        }
        headers = {"X-Webhook-Secret": settings.WEBHOOK_SHARED_SECRET}

        res = client.post("/intake/webhook", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["source"] == "webhook"
        assert data["duplicate"] is False
        assert data["service_request_id"] is not None

        # Verify InboundEvent in database
        event_repo = InboundEventRepository(test_db_session)
        event = event_repo.get_by_source_and_external_id("webhook", "hook-evt-001")
        assert event is not None
        assert event.status == "completed"

    def test_webhook_missing_secret_returns_401(self):
        payload = {
            "event_id": "hook-no-sec",
            "event_type": "service_request",
            "customer": {"name": "NoSecret"},
            "message": "Test message",
        }
        res = client.post("/intake/webhook", json=payload)
        assert res.status_code == 401
        assert "Invalid or missing X-Webhook-Secret" in res.json()["detail"]

    def test_webhook_invalid_secret_returns_401(self):
        payload = {
            "event_id": "hook-bad-sec",
            "event_type": "service_request",
            "customer": {"name": "BadSecret"},
            "message": "Test message",
        }
        res = client.post(
            "/intake/webhook",
            json=payload,
            headers={"X-Webhook-Secret": "completely-wrong-secret"},
        )
        assert res.status_code == 401

    def test_webhook_unsupported_event_type_returns_400(self):
        payload = {
            "event_id": "hook-bad-type",
            "event_type": "customer.survey_response",
            "customer": {"name": "SurveyUser"},
            "message": "I enjoyed the service",
        }
        res = client.post(
            "/intake/webhook",
            json=payload,
            headers={"X-Webhook-Secret": settings.WEBHOOK_SHARED_SECRET},
        )
        assert res.status_code == 400
        assert "Unsupported webhook event_type" in res.json()["detail"]

    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_webhook_duplicate_idempotency(
        self, mock_parse, test_db_session: Session
    ):
        payload = {
            "event_id": "hook-dup-002",
            "event_type": "service_request",
            "customer": {
                "name": "Webhook Bob",
                "email": "wh.bob@example.com",
            },
            "message": "Duplicate test message",
        }
        headers = {"X-Webhook-Secret": settings.WEBHOOK_SHARED_SECRET}

        # Delivery 1
        res1 = client.post("/intake/webhook", json=payload, headers=headers)
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["duplicate"] is False

        # Delivery 2 (Duplicate)
        res2 = client.post("/intake/webhook", json=payload, headers=headers)
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["duplicate"] is True
        assert data2["service_request_id"] == data1["service_request_id"]

    @patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=MOCK_PARSED_HVAC)
    def test_webhook_same_id_different_payload_conflicts(
        self, mock_parse, test_db_session: Session
    ):
        payload1 = {
            "event_id": "hook-conflict-003",
            "event_type": "service_request",
            "customer": {"name": "Webhook Conflict", "email": "wh.conf@example.com"},
            "message": "Original problem statement",
        }
        headers = {"X-Webhook-Secret": settings.WEBHOOK_SHARED_SECRET}

        res1 = client.post("/intake/webhook", json=payload1, headers=headers)
        assert res1.status_code == 201

        # Same event_id, different customer name & message
        payload2 = {
            **payload1,
            "customer": {"name": "Tampered Name", "email": "wh.conf@example.com"},
            "message": "Tampered message statement",
        }
        res2 = client.post("/intake/webhook", json=payload2, headers=headers)
        assert res2.status_code == 409
        assert "Inbound conflict" in res2.json()["detail"]


# ==============================================================================
# 5. Full End-to-End Workflow Regression Test via Fake Email
# ==============================================================================


class TestEndToEndIntakeWorkflow:
    @patch("fieldops.agent.nodes.parse_request.parse_service_request")
    def test_fake_email_end_to_end_full_pipeline_approval(
        self, mock_parse, test_db_session: Session
    ):
        """Verify that a Fake Email request flows all the way to waiting_for_approval proposal."""
        seed_customers(test_db_session)
        seed_technicians(test_db_session)
        test_db_session.commit()

        mock_parse.return_value = ParsedServiceRequest(
            service_type="HVAC",
            urgency="high",
            location="Shinjuku",
            required_skills=["HVAC"],
            preferred_time="tomorrow afternoon",
            problem_description="AC smells like burning",
        )

        email_payload = {
            "message_id": "e2e-mail-flow-777",
            "from_name": "Kenji Sato",
            "from_email": "kenji.sato@example.com",
            "subject": "Emergency: AC burning odor in Shinjuku",
            "body": "My AC stopped working and smells like burning. I am in Shinjuku tomorrow afternoon.",
        }

        res = client.post("/intake/fake-email", json=email_payload)
        assert res.status_code == 201
        data = res.json()

        assert data["source"] == "fake_email"
        assert data["workflow_status"] == "waiting_for_approval"
        assert data["service_request_id"] is not None
        assert data["details"]["appointment_proposal"] is not None
        proposal = data["details"]["appointment_proposal"]
        assert proposal["technician_name"] == "Ken Tanaka"
        assert proposal["start_time"] is not None
        assert proposal["end_time"] is not None

        # Verify audit logs
        event = InboundEventRepository(test_db_session).get_by_source_and_external_id("fake_email", "e2e-mail-flow-777")
        assert event is not None
        audit_repo = AuditLogRepository(test_db_session)
        logs = audit_repo.list_by_entity("inbound_event", str(event.id))
        received_logs = [log for log in logs if log.action == "inbound.received"]
        assert len(received_logs) >= 1
        completed_logs = [log for log in logs if log.action == "inbound.completed"]
        assert len(completed_logs) >= 1


# ==============================================================================
# 6. Failure Handling & Audit Tests
# ==============================================================================


class TestInboundFailureHandling:
    @patch("fieldops.agent.nodes.parse_request.parse_service_request")
    def test_workflow_llm_failure_marks_inbound_event_failed(
        self, mock_parse, test_db_session: Session
    ):
        mock_parse.side_effect = LLMCallError("Simulated OpenAI API 500 internal server error")

        email_payload = {
            "message_id": "fail-mail-500",
            "from_name": "Failure Test",
            "from_email": "fail@example.com",
            "subject": "Crash test",
            "body": "This request triggers LLM failure",
        }

        res = client.post("/intake/fake-email", json=email_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["workflow_status"] == "llm_failed"

        # Verify InboundEvent marked as failed
        event_repo = InboundEventRepository(test_db_session)
        event = event_repo.get_by_source_and_external_id("fake_email", "fail-mail-500")
        assert event is not None
        assert event.status == "failed"
        assert "Simulated OpenAI API 500" in (event.error_summary or "")
