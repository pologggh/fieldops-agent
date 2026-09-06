"""Integration, concurrency, and failure tests for Google Calendar external synchronization."""

from datetime import datetime, timedelta, timezone
import json
import os
from unittest.mock import MagicMock, patch
import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response
from sqlalchemy.orm import Session

from fieldops.application.service_lifecycle_service import ServiceLifecycleService
from fieldops.core.config import settings
from fieldops.db.models import (
    Appointment,
    AuditLog,
    Customer,
    IntegrationRecord,
    ServiceRequest,
    Technician,
)
from fieldops.integrations import (
    CalendarClient,
    CalendarEventCreate,
    CalendarEventResult,
    GoogleCalendarClient,
    set_calendar_client,
)
from fieldops.integrations.calendar.reconciliation import CalendarReconciliationService
from fieldops.tasks.celery_app import celery_app
from fieldops.tasks.integration_tasks import (
    cancel_appointment_calendar_event,
    sync_appointment_calendar,
)


def _make_http_error(status_code: int, message: str = "Error message", reason: str = "Error") -> HttpError:
    resp = Response({"status": str(status_code), "reason": reason})
    content = json.dumps({"error": {"code": status_code, "message": message, "status": reason}}).encode("utf-8")
    return HttpError(resp, content)


def _seed_appointment(session: Session, status: str = "scheduled") -> tuple[Customer, Technician, ServiceRequest, Appointment]:
    customer = Customer(
        name="Integration Customer",
        email="gcal.test@example.com",
        phone="+81-90-9876-5432",
    )
    session.add(customer)
    session.flush()

    technician = Technician(
        name="Field Specialist Taro",
        service_area="Tokyo-Chiyoda",
        status="active",
        max_daily_work_minutes=480,
    )
    session.add(technician)
    session.flush()

    sr = ServiceRequest(
        customer_id=customer.id,
        raw_message="Commercial chiller maintenance",
        service_type="HVAC Commercial",
        urgency="medium",
        location="Tokyo-Chiyoda 2-3-4",
        status=status,
    )
    session.add(sr)
    session.flush()

    now = datetime.now(timezone.utc)
    appt = Appointment(
        service_request_id=sr.id,
        technician_id=technician.id,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=2),
        status=status,
    )
    session.add(appt)
    session.flush()
    session.commit()
    return customer, technician, sr, appt


class TestGoogleCalendarE2ESync:
    """Validate full flow from DB appointment creation to Google Calendar sync."""

    def test_e2e_appointment_to_google_calendar_sync(self, test_db_session: Session) -> None:
        _, _, _, appt = _seed_appointment(test_db_session)

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.list.return_value.execute.return_value = {"items": []}
        mock_events.insert.return_value.execute.return_value = {
            "id": "gcal-synced-101",
            "status": "confirmed",
        }

        mock_client = GoogleCalendarClient(service=mock_service)
        set_calendar_client(mock_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            res = sync_appointment_calendar(appt.id)

        assert res["status"] == "synced"
        assert res["external_event_id"] == "gcal-synced-101"

        # Verify IntegrationRecord state
        record = (
            test_db_session.query(IntegrationRecord)
            .filter_by(provider="google_calendar", local_resource_id=appt.id)
            .first()
        )
        assert record is not None
        assert record.status == "synced"
        assert record.external_resource_id == "gcal-synced-101"
        assert record.attempt_count == 1

        # Verify Audit Logs
        audit_actions = [
            a.action
            for a in test_db_session.query(AuditLog)
            .filter_by(entity_type="appointment", entity_id=str(appt.id))
            .all()
        ]
        assert "calendar.sync_started" in audit_actions
        assert "calendar.synced" in audit_actions

        set_calendar_client(None)

    def test_appointment_cancellation_calendar_sync(self, test_db_session: Session) -> None:
        _, _, _, appt = _seed_appointment(test_db_session, status="cancelled")

        # Create existing synced IntegrationRecord
        rec = IntegrationRecord(
            provider="google_calendar",
            resource_type="appointment",
            local_resource_id=appt.id,
            external_resource_id="gcal-to-delete-555",
            status="synced",
            attempt_count=1,
        )
        test_db_session.add(rec)
        test_db_session.commit()

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.delete.return_value.execute.return_value = ""

        mock_client = GoogleCalendarClient(service=mock_service)
        set_calendar_client(mock_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            res = cancel_appointment_calendar_event(appt.id)

        assert res["status"] == "cancelled"
        mock_events.delete.assert_called_once()

        test_db_session.refresh(rec)
        assert rec.status == "cancelled"

        set_calendar_client(None)

    def test_appointment_reschedule_calendar_sync(self, test_db_session: Session) -> None:
        """Old appointment's event is cancelled, replacement appointment's event is created."""
        _, tech, sr, old_appt = _seed_appointment(test_db_session, status="scheduled")

        # Record for old appointment
        old_rec = IntegrationRecord(
            provider="google_calendar",
            resource_type="appointment",
            local_resource_id=old_appt.id,
            external_resource_id="gcal-old-appt",
            status="synced",
            attempt_count=1,
        )
        test_db_session.add(old_rec)
        test_db_session.commit()

        # Execute Reschedule via ServiceLifecycleService
        service = ServiceLifecycleService(test_db_session)
        resched_req = service.request_reschedule(
            service_request_id=sr.id,
            requested_by_type="customer",
            requested_by_id=str(sr.customer_id),
            preferred_time=datetime.now(timezone.utc) + timedelta(days=3),
            reason="Customer request",
        )

        new_start = datetime.now(timezone.utc) + timedelta(days=3, hours=10)
        new_end = new_start + timedelta(hours=2)
        approved_req, replacement_appt = service.approve_reschedule(
            reschedule_request_id=resched_req.id,
            start_time=new_start,
            end_time=new_end,
            technician_id=tech.id,
            operator_id="lead.operator@example.com",
        )

        new_appt_id = replacement_appt.id
        assert new_appt_id is not None

        # Setup mock for Google Calendar
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.delete.return_value.execute.return_value = ""
        mock_events.list.return_value.execute.return_value = {"items": []}
        mock_events.insert.return_value.execute.return_value = {
            "id": "gcal-new-appt",
            "status": "confirmed",
        }

        mock_client = GoogleCalendarClient(service=mock_service)
        set_calendar_client(mock_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            # Old appointment gets cancelled
            cancel_res = cancel_appointment_calendar_event(old_appt.id)
            assert cancel_res["status"] == "cancelled"

            # New appointment gets synced
            sync_res = sync_appointment_calendar(new_appt_id)
            assert sync_res["status"] == "synced"
            assert sync_res["external_event_id"] == "gcal-new-appt"

        test_db_session.refresh(old_rec)
        assert old_rec.status == "cancelled"

        new_rec = (
            test_db_session.query(IntegrationRecord)
            .filter_by(provider="google_calendar", local_resource_id=new_appt_id)
            .first()
        )
        assert new_rec is not None
        assert new_rec.status == "synced"
        assert new_rec.external_resource_id == "gcal-new-appt"

        set_calendar_client(None)


class TestCrashAfterProviderSuccessIdempotency:
    """Simulate worker crash after Google returns 200 but before DB commit."""

    def test_crash_after_provider_success_recovers_without_duplicate(self, test_db_session: Session) -> None:
        _, _, _, appt = _seed_appointment(test_db_session)

        # Track Google Calendar event creation
        stored_events: dict[str, dict] = {}

        class SimulatedGoogleCalendarClient(CalendarClient):
            def __init__(self) -> None:
                self.insert_count = 0

            def create_event(self, event: CalendarEventCreate) -> CalendarEventResult:
                # 1. Provider-side correlation lookup:
                for eid, e in stored_events.items():
                    if e.get("appointment_id") == event.appointment_id:
                        # Found existing event!
                        return CalendarEventResult(
                            external_event_id=eid,
                            status="confirmed",
                            provider="google_calendar",
                        )

                # 2. Insert if not found:
                self.insert_count += 1
                eid = f"gcal-crash-proof-{event.appointment_id}"
                stored_events[eid] = {
                    "id": eid,
                    "appointment_id": event.appointment_id,
                    "status": "confirmed",
                }
                return CalendarEventResult(
                    external_event_id=eid,
                    status="confirmed",
                    provider="google_calendar",
                )

            def get_event(self, external_event_id: str) -> CalendarEventResult | None:
                if external_event_id in stored_events:
                    return CalendarEventResult(
                        external_event_id=external_event_id,
                        status="confirmed",
                        provider="google_calendar",
                    )
                return None

            def cancel_event(self, external_event_id: str) -> bool:
                stored_events.pop(external_event_id, None)
                return True

        sim_client = SimulatedGoogleCalendarClient()
        set_calendar_client(sim_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            # RUN 1: Simulates Google creation succeeding, but DB crashing right before commit
            with patch.object(
                Session, "commit", side_effect=[None, None, Exception("Simulated Worker Crash before DB Commit")]
            ):
                try:
                    sync_appointment_calendar(appt.id)
                except Exception:
                    pass  # Worker crashed!

            # At this point, the Google event was created:
            assert sim_client.insert_count == 1
            assert f"gcal-crash-proof-{appt.id}" in stored_events

            # RUN 2: Celery retries the task after the crash
            res = sync_appointment_calendar(appt.id)

            assert res["status"] == "synced"
            assert res["external_event_id"] == f"gcal-crash-proof-{appt.id}"

            # CRITICAL ASSERTION: insert was NOT called again! Exactly 1 event exists on Google!
            assert sim_client.insert_count == 1
            assert len(stored_events) == 1

        set_calendar_client(None)


class TestConcurrencyAndFailureIsolation:
    """Validate zero business facts rollback on external API failure, and duplicate task safety."""

    def test_duplicate_concurrent_tasks_create_single_event(self, test_db_session: Session) -> None:
        _, _, _, appt = _seed_appointment(test_db_session)

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.list.return_value.execute.return_value = {"items": []}
        mock_events.insert.return_value.execute.return_value = {
            "id": "gcal-single-100",
            "status": "confirmed",
        }

        mock_client = GoogleCalendarClient(service=mock_service)
        set_calendar_client(mock_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            res1 = sync_appointment_calendar(appt.id)
            assert res1["status"] == "synced"

            # Second execution of task
            res2 = sync_appointment_calendar(appt.id)
            assert res2["status"] == "already_synced"

        # mock insert called exactly once
        mock_events.insert.assert_called_once()
        set_calendar_client(None)

    def test_google_calendar_failure_does_not_rollback_appointment(self, test_db_session: Session) -> None:
        """External 503 outage fails integration sync, but PostgreSQL appointment remains intact."""
        _, _, _, appt = _seed_appointment(test_db_session)
        assert appt.status == "scheduled"

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.list.return_value.execute.return_value = {"items": []}
        mock_events.insert.return_value.execute.side_effect = _make_http_error(503, "Google Backend Outage")

        mock_client = GoogleCalendarClient(service=mock_service)
        set_calendar_client(mock_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            with pytest.raises(Exception):
                sync_appointment_calendar(appt.id)

        # Re-query appointment from database
        test_db_session.expire_all()
        refreshed_appt = test_db_session.get(Appointment, appt.id)
        assert refreshed_appt is not None
        # Appointment MUST remain valid and scheduled
        assert refreshed_appt.status == "scheduled"

        set_calendar_client(None)


class TestCalendarReconciliationService:
    """Verify drift detection and self-healing between database and Google Calendar."""

    def test_reconciliation_detects_missing_remote_event(self, test_db_session: Session) -> None:
        _, _, _, appt = _seed_appointment(test_db_session, status="scheduled")

        rec = IntegrationRecord(
            provider="google_calendar",
            resource_type="appointment",
            local_resource_id=appt.id,
            external_resource_id="gcal-deleted-by-human",
            status="synced",
            attempt_count=1,
        )
        test_db_session.add(rec)
        test_db_session.commit()

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        # get returns 404
        mock_events.get.return_value.execute.side_effect = _make_http_error(404, "Not Found")

        mock_client = GoogleCalendarClient(service=mock_service)
        recon_service = CalendarReconciliationService(test_db_session, calendar_client=mock_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            drift_res = recon_service.reconcile_appointment(appt.id, auto_heal=False)

        assert drift_res["drift"] == "missing_remote"
        assert drift_res["status"] == "drift_detected"

    def test_reconciliation_detects_and_cancels_remote_for_cancelled_appointment(
        self, test_db_session: Session
    ) -> None:
        _, _, _, appt = _seed_appointment(test_db_session, status="cancelled")

        rec = IntegrationRecord(
            provider="google_calendar",
            resource_type="appointment",
            local_resource_id=appt.id,
            external_resource_id="gcal-still-alive",
            status="synced",
            attempt_count=1,
        )
        test_db_session.add(rec)
        test_db_session.commit()

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        # get returns active event
        mock_events.get.return_value.execute.return_value = {"id": "gcal-still-alive", "status": "confirmed"}
        mock_events.delete.return_value.execute.return_value = ""

        mock_client = GoogleCalendarClient(service=mock_service)
        recon_service = CalendarReconciliationService(test_db_session, calendar_client=mock_client)

        with patch.object(settings, "CALENDAR_PROVIDER", "google"):
            drift_res = recon_service.reconcile_appointment(appt.id, auto_heal=True)

        assert drift_res["drift"] == "cancelled_appointment_active_remote"
        assert drift_res["status"] == "drift_repaired"
        mock_events.delete.assert_called_once()

        test_db_session.refresh(rec)
        assert rec.status == "cancelled"


@pytest.mark.skipif(
    os.getenv("RUN_GOOGLE_INTEGRATION_TESTS") != "true",
    reason="Live Google Calendar integration tests require RUN_GOOGLE_INTEGRATION_TESTS=true",
)
class TestLiveGoogleCalendarSmoke:
    """Smoke test running against actual Google Calendar API when environment credentials provided."""

    def test_live_calendar_create_get_cancel_cycle(self) -> None:
        client = GoogleCalendarClient()
        appt_id = 99999
        now = datetime.now(timezone.utc)

        event_dto = CalendarEventCreate(
            appointment_id=appt_id,
            title="Live Test Smoke Appointment",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            location="Live Integration Test Facility",
            description="Automated Smoke Verification",
        )

        # 1. Create
        res = client.create_event(event_dto)
        assert res.external_event_id is not None
        assert res.provider == "google_calendar"

        # 2. Get
        fetched = client.get_event(res.external_event_id)
        assert fetched is not None
        assert fetched.external_event_id == res.external_event_id

        # 3. Cancel
        cancelled = client.cancel_event(res.external_event_id)
        assert cancelled is True

        # 4. Confirm Gone
        confirm = client.get_event(res.external_event_id)
        assert confirm is None or confirm.status == "cancelled"
