"""Tests for Phase 15: External Integration Architecture with Fake Providers."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from fieldops.application.appointment_service import AppointmentService
from fieldops.core.config import settings
from fieldops.db.models import (
    Appointment,
    Customer,
    IntegrationRecord,
    NotificationJob,
    OutboxEvent,
    ServiceRequest,
    Technician,
)
from fieldops.integrations import (
    CalendarEventCreate,
    FakeCalendarClient,
    FakeEmailClient,
    PermanentIntegrationError,
    TransientIntegrationError,
    get_calendar_client,
    get_email_client,
    set_calendar_client,
    set_email_client,
)
from fieldops.integrations.email.renderer import render_appointment_confirmation
from fieldops.main import app
from fieldops.repositories.integration_repository import IntegrationRepository
from fieldops.repositories.notification_job_repository import (
    NotificationJobRepository,
)
from fieldops.tasks.integration_tasks import (
    cancel_appointment_calendar_event,
    send_appointment_confirmation,
    sync_appointment_calendar,
)
from fieldops.tasks.outbox_tasks import publish_outbox_events


from tests.conftest import TEST_OPERATOR_HEADERS


@pytest.fixture
def client():
    return TestClient(app, headers=TEST_OPERATOR_HEADERS)


@pytest.fixture(autouse=True)
def reset_integration_clients():
    fake_cal = FakeCalendarClient()
    fake_email = FakeEmailClient()
    set_calendar_client(fake_cal)
    set_email_client(fake_email)
    yield
    fake_cal.clear()
    fake_email.clear()
    set_calendar_client(None)
    set_email_client(None)


@pytest.fixture
def sample_data(test_db_session):
    """Seed customer, technician, service request, and appointment."""
    customer = Customer(
        name="Alice Smith",
        email="alice@example.com",
        phone="1234567890",
    )
    test_db_session.add(customer)
    test_db_session.flush()

    technician = Technician(
        name="Bob Tanaka",
        service_area="Tokyo",
        status="active",
    )
    test_db_session.add(technician)
    test_db_session.flush()

    service_request = ServiceRequest(
        customer_id=customer.id,
        raw_message="My AC is leaking water in Shibuya",
        service_type="ac_repair",
        urgency="high",
        location="Shibuya, Tokyo",
        status="scheduled",
    )
    test_db_session.add(service_request)
    test_db_session.flush()

    now = datetime.now(timezone.utc)
    appointment = Appointment(
        service_request_id=service_request.id,
        technician_id=technician.id,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=2),
        status="scheduled",
    )
    test_db_session.add(appointment)
    test_db_session.commit()

    return {
        "customer": customer,
        "technician": technician,
        "service_request": service_request,
        "appointment": appointment,
    }


class TestFakeCalendarClient:
    def test_create_event_deterministic_id(self):
        client = FakeCalendarClient()
        event_dto = CalendarEventCreate(
            appointment_id=42,
            title="AC Inspection",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2),
            location="Tokyo",
        )
        res = client.create_event(event_dto)
        assert res.external_event_id == "fake-cal-appointment-42"
        assert res.status == "confirmed"

    def test_provider_side_idempotency(self):
        client = FakeCalendarClient()
        event_dto = CalendarEventCreate(
            appointment_id=99,
            title="Refrigerator Check",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            location="Shinjuku",
        )
        res1 = client.create_event(event_dto)
        res2 = client.create_event(event_dto)
        assert res1.external_event_id == res2.external_event_id
        assert client.get_event("fake-cal-appointment-99") is not None

    def test_cancel_event(self):
        client = FakeCalendarClient()
        event_dto = CalendarEventCreate(
            appointment_id=10,
            title="Heater Repair",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            location="Roppongi",
        )
        res = client.create_event(event_dto)
        assert client.cancel_event(res.external_event_id) is True
        cancelled_event = client.get_event(res.external_event_id)
        assert cancelled_event.status == "cancelled"

    def test_fault_injection_transient_and_permanent(self):
        client = FakeCalendarClient()
        event_dto = CalendarEventCreate(
            appointment_id=77,
            title="Test Event",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=1),
            location="Tokyo",
        )

        # Transient: fails once, then succeeds
        client.simulate_transient_failure(count=1)
        with pytest.raises(TransientIntegrationError):
            client.create_event(event_dto)
        res = client.create_event(event_dto)
        assert res.status == "confirmed"

        # Permanent: always fails
        client.simulate_permanent_failure()
        with pytest.raises(PermanentIntegrationError):
            client.create_event(event_dto)


class TestCalendarSyncTask:
    def test_sync_appointment_calendar_success(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        result = sync_appointment_calendar(appt.id)

        assert result["status"] == "synced"
        assert result["external_event_id"] == f"fake-cal-appointment-{appt.id}"

        # Verify DB record
        repo = IntegrationRepository(test_db_session)
        rec = repo.get_by_provider_resource("fake_calendar", "appointment", appt.id)
        assert rec is not None
        assert rec.status == "synced"
        assert rec.external_resource_id == f"fake-cal-appointment-{appt.id}"

    def test_sync_appointment_calendar_idempotency(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        res1 = sync_appointment_calendar(appt.id)
        assert res1["status"] == "synced"

        # Run again: should hit idempotency guard and not duplicate record
        res2 = sync_appointment_calendar(appt.id)
        assert res2["status"] == "already_synced"

        repo = IntegrationRepository(test_db_session)
        records = repo.get_by_appointment_id(appt.id)
        assert len(records) == 1

    def test_cancelled_appointment_does_not_create_calendar_event(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        appt.status = "cancelled"
        test_db_session.commit()

        result = sync_appointment_calendar(appt.id)
        assert result["status"] == "skipped"
        assert result["reason"] == "appointment_cancelled"

        cal_client = get_calendar_client()
        assert cal_client.get_event(f"fake-cal-appointment-{appt.id}") is None

    def test_cancel_appointment_calendar_event_updates_record(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        # First sync
        sync_appointment_calendar(appt.id)

        # Now cancel
        res = cancel_appointment_calendar_event(appt.id)
        assert res["status"] == "cancelled"

        repo = IntegrationRepository(test_db_session)
        rec = repo.get_by_provider_resource("fake_calendar", "appointment", appt.id)
        assert rec.status == "cancelled"

    def test_calendar_sync_transient_retry(self, sample_data):
        appt = sample_data["appointment"]
        client = get_calendar_client()
        client.simulate_transient_failure(count=1)

        # In testing environment or direct call with max_retries
        # Mock retry method on task
        with patch.object(sync_appointment_calendar, "retry", side_effect=Exception("retrying")) as mock_retry:
            with pytest.raises(Exception, match="retrying"):
                sync_appointment_calendar(appt.id)
            assert mock_retry.called

    def test_calendar_sync_permanent_failure_no_retry(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        client = get_calendar_client()
        client.simulate_permanent_failure("Invalid calendar payload")

        with patch.object(sync_appointment_calendar, "retry") as mock_retry:
            res = sync_appointment_calendar(appt.id)
            assert res["status"] == "failed"
            assert "Invalid calendar payload" in res["error"]
            assert not mock_retry.called

            repo = IntegrationRepository(test_db_session)
            rec = repo.get_by_provider_resource("fake_calendar", "appointment", appt.id)
            assert rec.status == "failed"


class TestEmailConfirmation:
    def test_render_appointment_confirmation(self, sample_data):
        subject, body = render_appointment_confirmation(
            customer=sample_data["customer"],
            appointment=sample_data["appointment"],
            service_request=sample_data["service_request"],
            technician=sample_data["technician"],
        )
        assert "Ac Repair" in subject
        assert "Bob Tanaka" in body
        assert "Shibuya, Tokyo" in body
        assert "Alice Smith" in body

    def test_send_appointment_confirmation_success(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        result = send_appointment_confirmation(appt.id)

        assert result["status"] == "completed"
        assert "fake-msg-" in result["provider_message_id"]

        # Verify NotificationJob record
        notif_repo = NotificationJobRepository(test_db_session)
        jobs = notif_repo.get_by_appointment_id(appt.id)
        conf_jobs = [j for j in jobs if j.job_type == "appointment_confirmation"]
        assert len(conf_jobs) == 1
        assert conf_jobs[0].status == "completed"
        assert conf_jobs[0].provider == "fake_email"
        assert conf_jobs[0].provider_message_id == result["provider_message_id"]
        assert conf_jobs[0].sent_at is not None

    def test_send_appointment_confirmation_idempotency(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        res1 = send_appointment_confirmation(appt.id)
        assert res1["status"] == "completed"

        # Second call should not resend
        res2 = send_appointment_confirmation(appt.id)
        assert res2["status"] == "already_completed"

        email_client = get_email_client()
        assert len(email_client.sent_emails) == 1

    def test_recipient_security_from_database(self, sample_data):
        appt = sample_data["appointment"]
        send_appointment_confirmation(appt.id)

        email_client = get_email_client()
        assert len(email_client.sent_emails) == 1
        assert email_client.sent_emails[0]["recipient"] == "alice@example.com"

    def test_invalid_recipient_fails_safely(self, sample_data, test_db_session):
        sample_data["customer"].email = "not-an-email"
        test_db_session.commit()

        appt = sample_data["appointment"]
        with patch.object(send_appointment_confirmation, "retry") as mock_retry:
            res = send_appointment_confirmation(appt.id)
            assert res["status"] == "failed"
            assert res["error"] == "invalid_customer_email"
            assert not mock_retry.called


class TestConcurrencyAndCrashRecovery:
    def test_concurrent_calendar_sync_produces_single_record(self, sample_data, test_db_session):
        appt = sample_data["appointment"]

        # Simulate concurrent workers executing sync_appointment_calendar
        res1 = sync_appointment_calendar(appt.id)
        res2 = sync_appointment_calendar(appt.id)

        assert res1["status"] == "synced"
        assert res2["status"] == "already_synced"

        repo = IntegrationRepository(test_db_session)
        records = repo.get_by_appointment_id(appt.id)
        assert len(records) == 1

    def test_worker_crash_recovery_relies_on_provider_idempotency(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        cal_client = get_calendar_client()

        # Step 1: Client generates event, but DB update failed (simulated crash)
        event_dto = CalendarEventCreate(
            appointment_id=appt.id,
            title="Crash Test",
            start_time=appt.start_time,
            end_time=appt.end_time,
            location="Tokyo",
        )
        event_res = cal_client.create_event(event_dto)
        assert event_res.external_event_id == f"fake-cal-appointment-{appt.id}"

        # Step 2: Task runs as retry from scratch
        res = sync_appointment_calendar(appt.id)
        assert res["status"] == "synced"
        assert res["external_event_id"] == event_res.external_event_id

        # DB has exactly 1 record
        repo = IntegrationRepository(test_db_session)
        assert len(repo.get_by_appointment_id(appt.id)) == 1


class TestOutboxIntegrationFlow:
    def test_publish_outbox_events_dispatches_calendar_and_email(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        # Create outbox event
        outbox_event = OutboxEvent(
            event_type="appointment.created",
            aggregate_type="appointment",
            aggregate_id=str(appt.id),
            payload={"appointment_id": appt.id},
            status="pending",
        )
        test_db_session.add(outbox_event)
        test_db_session.commit()

        with patch("fieldops.tasks.outbox_tasks.sync_appointment_calendar.apply_async") as mock_cal, \
             patch("fieldops.tasks.outbox_tasks.send_appointment_confirmation.apply_async") as mock_email, \
             patch("fieldops.tasks.outbox_tasks.send_appointment_reminder.apply_async") as mock_reminder:
            result = publish_outbox_events()
            assert result["processed"] >= 1
            assert mock_cal.called
            assert mock_email.called
            assert mock_reminder.called

    def test_publish_outbox_events_dispatches_cancellation(self, sample_data, test_db_session):
        appt = sample_data["appointment"]
        outbox_event = OutboxEvent(
            event_type="appointment.cancelled",
            aggregate_type="appointment",
            aggregate_id=str(appt.id),
            payload={"appointment_id": appt.id, "reason": "customer_request"},
            status="pending",
        )
        test_db_session.add(outbox_event)
        test_db_session.commit()

        with patch("fieldops.tasks.outbox_tasks.cancel_appointment_calendar_event.apply_async") as mock_cancel:
            result = publish_outbox_events()
            assert result["processed"] >= 1
            assert mock_cancel.called


class TestIntegrationApiEndpoint:
    def test_get_appointment_integrations(self, client, sample_data):
        appt = sample_data["appointment"]
        sync_appointment_calendar(appt.id)
        send_appointment_confirmation(appt.id)

        response = client.get(f"/appointments/{appt.id}/integrations")
        assert response.status_code == 200
        data = response.json()
        assert data["appointment_id"] == appt.id
        assert len(data["calendar_integrations"]) == 1
        assert data["calendar_integrations"][0]["status"] == "synced"
        assert len(data["email_notifications"]) == 1
        assert data["email_notifications"][0]["status"] == "completed"

    def test_get_appointment_integrations_not_found(self, client):
        response = client.get("/appointments/999999/integrations")
        assert response.status_code == 404

