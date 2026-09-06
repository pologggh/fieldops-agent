"""Unit and integration tests for Phase 12: Async Jobs, Outbox Pattern, and Redis/Celery."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.application.appointment_service import AppointmentService
from fieldops.core.config import settings
from fieldops.db.models import Appointment, NotificationJob, OutboxEvent
from fieldops.main import app
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.notification_job_repository import (
    NotificationJobRepository,
)
from fieldops.repositories.outbox_repository import OutboxRepository
from fieldops.repositories.service_request_repository import (
    ServiceRequestRepository,
)
from fieldops.tasks.appointment_tasks import (
    send_appointment_reminder,
    send_followup_message,
)
from fieldops.tasks.outbox_tasks import (
    calculate_reminder_time,
    publish_outbox_events,
)
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)
TZ = ZoneInfo(settings.BUSINESS_TIMEZONE)


def _setup_service_request(session: Session) -> tuple[int, int]:
    """Helper to seed customers, technicians, and a service request."""
    seed_customers(session)
    seed_technicians(session)
    session.commit()
    sr_repo = ServiceRequestRepository(session)
    sr = sr_repo.create(
        customer_id=1,
        raw_message="AC stopped cooling in Shinjuku",
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        status="pending",
    )
    session.commit()
    return sr.id, 1


# ==============================================================================
# 1. Outbox Atomicity Tests
# ==============================================================================


def test_outbox_atomicity_on_success(test_db_session: Session) -> None:
    """OutboxEvent and Appointment are committed atomically in the same transaction."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 10, 10, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 10, 12, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    result = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    assert result.success is True
    assert result.appointment_id is not None

    # Verify Appointment exists
    appt_repo = AppointmentRepository(test_db_session)
    appt = appt_repo.get_by_id(result.appointment_id)
    assert appt is not None
    assert appt.status == "scheduled"

    # Verify OutboxEvent exists in the exact same transaction
    outbox_repo = OutboxRepository(test_db_session)
    pending_events = outbox_repo.get_pending()
    assert len(pending_events) == 1
    event = pending_events[0]
    assert event.event_type == "appointment.created"
    assert event.aggregate_type == "appointment"
    assert event.aggregate_id == str(result.appointment_id)
    assert event.payload == {"appointment_id": result.appointment_id}
    assert event.status == "pending"


def test_outbox_atomicity_on_conflict_no_event(test_db_session: Session) -> None:
    """When a conflict occurs, no OutboxEvent for appointment.created is generated."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 10, 10, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 10, 12, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    # First booking succeeds
    res1 = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    assert res1.success is True

    # Second booking for different SR with overlapping time encounters conflict
    sr_repo = ServiceRequestRepository(test_db_session)
    sr2 = sr_repo.create(
        customer_id=1,
        raw_message="Second inquiry",
        service_type="HVAC",
        urgency="medium",
        location="Shinjuku",
        status="pending",
    )
    test_db_session.commit()

    res2 = service.finalize_appointment(
        service_request_id=sr2.id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    assert res2.success is False
    assert res2.conflict_detected is True

    # Only 1 outbox event exists (from the first successful booking)
    outbox_repo = OutboxRepository(test_db_session)
    events = test_db_session.execute(
        select(OutboxEvent).where(OutboxEvent.aggregate_id == str(sr2.id))
    ).scalars().all()
    assert len(events) == 0


# ==============================================================================
# 2. Outbox Publisher Tests
# ==============================================================================


@patch("fieldops.tasks.outbox_tasks.sync_appointment_calendar.apply_async")
@patch("fieldops.tasks.outbox_tasks.send_appointment_confirmation.apply_async")
@patch("fieldops.tasks.outbox_tasks.send_appointment_reminder.apply_async")
def test_outbox_publisher_success(
    mock_reminder: MagicMock,
    mock_email: MagicMock,
    mock_cal: MagicMock,
    test_db_session: Session,
) -> None:
    """Publisher picks up pending events, dispatches tasks, and marks events as processed."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 12, 14, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 12, 16, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    result = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )

    outbox_repo = OutboxRepository(test_db_session)
    pending_before = outbox_repo.get_pending()
    assert len(pending_before) == 1
    event_id = pending_before[0].id

    # Run publisher
    publish_result = publish_outbox_events(limit=10)
    assert publish_result["processed"] == 1
    assert publish_result["failed"] == 0

    # Verify task dispatch
    assert mock_cal.called
    assert mock_email.called
    assert mock_reminder.called
    kwargs = mock_reminder.call_args[1]["kwargs"]
    assert kwargs["appointment_id"] == result.appointment_id

    # Verify event marked as processed in DB
    test_db_session.expire_all()
    event_after = outbox_repo.get(event_id)
    assert event_after is not None
    assert event_after.status == "processed"
    assert event_after.processed_at is not None



@patch("fieldops.tasks.outbox_tasks.sync_appointment_calendar.apply_async")
@patch("fieldops.tasks.outbox_tasks.send_appointment_confirmation.apply_async")
@patch("fieldops.tasks.outbox_tasks.send_appointment_reminder.apply_async")
def test_outbox_publisher_broker_down_preserves_event(
    mock_reminder: MagicMock,
    mock_email: MagicMock,
    mock_cal: MagicMock,
    test_db_session: Session,
) -> None:
    """If broker dispatch fails (Redis down), OutboxEvent remains pending and is not lost."""
    mock_cal.side_effect = ConnectionError("Could not connect to Redis broker at localhost:6379")

    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 12, 14, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 12, 16, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )

    # Run publisher
    publish_result = publish_outbox_events(limit=10)
    assert publish_result["processed"] == 0
    assert publish_result["failed"] == 1

    # Verify event remains strictly in status='pending'
    outbox_repo = OutboxRepository(test_db_session)
    pending_events = outbox_repo.get_pending()
    assert len(pending_events) == 1
    assert pending_events[0].status == "pending"


# ==============================================================================
# 3. Reminder Task Idempotency Tests
# ==============================================================================


def test_reminder_task_idempotency(test_db_session: Session) -> None:
    """Duplicate execution of send_appointment_reminder does not send duplicate notifications."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 15, 10, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 15, 12, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    res = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    appt_id = res.appointment_id
    sched_iso = (start_dt - timedelta(hours=24)).isoformat()

    # First execution: successfully executes reminder
    result1 = send_appointment_reminder.apply(
        kwargs={"appointment_id": appt_id, "scheduled_for_iso": sched_iso}
    ).get()

    assert result1["status"] == "completed"
    assert result1["attempt_count"] == 1

    # Check notification_jobs table
    test_db_session.expire_all()
    notif_repo = NotificationJobRepository(test_db_session)
    jobs = notif_repo.get_by_appointment_id(appt_id)
    assert len(jobs) == 1
    assert jobs[0].status == "completed"

    # Second execution (e.g. redelivery / duplicate ACK): hits idempotency guard
    result2 = send_appointment_reminder.apply(
        kwargs={"appointment_id": appt_id, "scheduled_for_iso": sched_iso}
    ).get()

    assert result2["status"] == "already_completed"

    # Still only 1 record exists in DB
    test_db_session.expire_all()
    jobs_after = notif_repo.get_by_appointment_id(appt_id)
    assert len(jobs_after) == 1



# ==============================================================================
# 4. Status Guard: Cancelled Appointment
# ==============================================================================


def test_reminder_task_skips_cancelled_appointment(test_db_session: Session) -> None:
    """If appointment is cancelled before reminder runs, task marks status as skipped."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 16, 14, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 16, 16, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    res = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    appt_id = res.appointment_id

    # Customer or operator cancels the appointment
    service.cancel_appointment(appt_id, reason="Customer called to cancel")

    sched_iso = (start_dt - timedelta(hours=24)).isoformat()

    # Execute reminder
    result = send_appointment_reminder.apply(
        kwargs={"appointment_id": appt_id, "scheduled_for_iso": sched_iso}
    ).get()

    assert result["status"] == "skipped"
    assert result["reason"] == "appointment_cancelled"

    # Verify notification_job record in DB is skipped
    test_db_session.expire_all()
    notif_repo = NotificationJobRepository(test_db_session)
    jobs = notif_repo.get_by_appointment_id(appt_id)
    assert len(jobs) == 1
    assert jobs[0].status == "skipped"
    assert jobs[0].last_error == "appointment_cancelled"


# ==============================================================================
# 5. Follow-up Notification Task
# ==============================================================================


@patch("fieldops.tasks.outbox_tasks.send_appointment_reminder.apply_async")
@patch("fieldops.tasks.outbox_tasks.send_followup_message.apply_async")
def test_appointment_completion_and_followup_flow(
    mock_followup_apply_async: MagicMock,
    mock_reminder_apply_async: MagicMock,
    test_db_session: Session,
) -> None:

    """Completing an appointment creates an outbox event, and followup task executes."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 10, 10, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 10, 12, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    res = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    appt_id = res.appointment_id

    # Mark appointment completed
    service.complete_appointment(appt_id)

    # Verify outbox event created
    outbox_repo = OutboxRepository(test_db_session)
    completed_events = [
        e for e in outbox_repo.get_pending() if e.event_type == "appointment.completed"
    ]
    assert len(completed_events) == 1
    assert completed_events[0].payload["appointment_id"] == appt_id

    # Run outbox publisher
    publish_outbox_events()
    assert mock_followup_apply_async.called
    assert mock_followup_apply_async.call_args[1]["countdown"] == 3600

    # Execute followup task directly
    followup_result = send_followup_message.apply(
        kwargs={"appointment_id": appt_id}
    ).get()
    assert followup_result["status"] == "completed"

    test_db_session.expire_all()
    notif_repo = NotificationJobRepository(test_db_session)
    followup_jobs = [
        j for j in notif_repo.get_by_appointment_id(appt_id) if j.job_type == "followup_message"
    ]
    assert len(followup_jobs) == 1
    assert followup_jobs[0].status == "completed"


# ==============================================================================
# 6. Reminder Time Calculation Unit Tests
# ==============================================================================


def test_calculate_reminder_time_rules() -> None:
    """Verify 24h, 1h, and immediate fallback reminder calculation rules."""
    now = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    # 1. More than 24 hours away: schedule for start - 24h
    start_48h = now + timedelta(hours=48)
    rem_48h = calculate_reminder_time(start_48h, now=now)
    assert rem_48h == start_48h - timedelta(hours=24)

    # 2. Between 1h and 24h away (e.g. 10 hours): schedule for start - 1h
    start_10h = now + timedelta(hours=10)
    rem_10h = calculate_reminder_time(start_10h, now=now)
    assert rem_10h == start_10h - timedelta(hours=1)

    # 3. Less than 1 hour away (e.g. 30 mins): schedule immediately (now)
    start_30m = now + timedelta(minutes=30)
    rem_30m = calculate_reminder_time(start_30m, now=now)
    assert rem_30m == now


# ==============================================================================
# 7. FastAPI Notification API Endpoint Tests
# ==============================================================================


def test_api_notification_queries_and_lifecycle(test_db_session: Session) -> None:
    """Verify HTTP endpoints for notifications query, complete, and cancel."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 20, 10, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 20, 12, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    res = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    appt_id = res.appointment_id

    # Create a notification job
    send_appointment_reminder.apply(kwargs={"appointment_id": appt_id}).get()

    # Query notifications via GET /appointments/{id}/notifications
    resp = client.get(f"/appointments/{appt_id}/notifications")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 1
    assert jobs[0]["appointment_id"] == appt_id
    assert jobs[0]["job_type"] == "appointment_reminder"
    assert jobs[0]["status"] == "completed"

    # Complete appointment via POST /appointments/{id}/complete
    comp_resp = client.post(f"/appointments/{appt_id}/complete")
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "completed"

    # Cancel endpoint test on a scheduled appointment
    sr_id2, tech_id2 = _setup_service_request(test_db_session)
    res2 = service.finalize_appointment(
        service_request_id=sr_id2,
        technician_id=tech_id2,
        start_time=start_dt + timedelta(days=1),
        end_time=end_dt + timedelta(days=1),
    )
    appt_id2 = res2.appointment_id
    cancel_resp = client.post(
        f"/appointments/{appt_id2}/cancel",
        json={"reason": "Customer cancelled"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


# ==============================================================================
# 8. Task Retry and Failure Recovery Tests
# ==============================================================================


def test_reminder_task_transient_retry_and_recovery(test_db_session: Session) -> None:
    """Simulate a transient failure on attempt 1, followed by a successful retry on attempt 2."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 22, 10, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 22, 12, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    res = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    appt_id = res.appointment_id
    sched_iso = (start_dt - timedelta(hours=24)).isoformat()

    # Mock transient failure on first attempt, recovery on second attempt
    with patch("fieldops.tasks.appointment_tasks.logger.info") as mock_log:
        mock_log.side_effect = [ConnectionResetError("Connection reset by peer"), None, None, None, None]
        res = send_appointment_reminder.apply(
            kwargs={"appointment_id": appt_id, "scheduled_for_iso": sched_iso},
            throw=False,
        ).get()

    assert res["status"] == "completed"
    assert res["attempt_count"] == 2

    # Check notification_jobs in DB: completed after recovery, attempt_count=2
    test_db_session.expire_all()
    notif_repo = NotificationJobRepository(test_db_session)
    jobs = notif_repo.get_by_appointment_id(appt_id)
    assert len(jobs) == 1
    assert jobs[0].status == "completed"
    assert jobs[0].attempt_count == 2



def test_reminder_task_max_retries_exceeded(test_db_session: Session) -> None:
    """When retries are exhausted, task permanently marks NotificationJob as failed."""
    sr_id, tech_id = _setup_service_request(test_db_session)
    start_dt = datetime(2026, 9, 25, 10, 0, tzinfo=TZ)
    end_dt = datetime(2026, 9, 25, 12, 0, tzinfo=TZ)

    service = AppointmentService(test_db_session)
    res = service.finalize_appointment(
        service_request_id=sr_id,
        technician_id=tech_id,
        start_time=start_dt,
        end_time=end_dt,
    )
    appt_id = res.appointment_id
    sched_iso = (start_dt - timedelta(hours=24)).isoformat()

    # Simulate 3 failed retries already executed, now at max_retries
    with patch("fieldops.tasks.appointment_tasks.logger.info") as mock_log:
        mock_log.side_effect = TimeoutError("Simulated persistent gateway timeout")
        res_fail = send_appointment_reminder.apply(
            kwargs={"appointment_id": appt_id, "scheduled_for_iso": sched_iso},
            retries=3,  # already hit max_retries (3)
            throw=False,
        ).get()

    assert res_fail["status"] == "failed"
    assert res_fail["error"] == "max_retries_exceeded"

    test_db_session.expire_all()
    notif_repo = NotificationJobRepository(test_db_session)
    jobs = notif_repo.get_by_appointment_id(appt_id)
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert "max_retries_exceeded" in (jobs[0].last_error or "")

