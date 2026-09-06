"""Concurrency and idempotency verification for Phase 24 Service Lifecycle Completion.

Validates:
- Double Complete idempotency (no duplicate outbox events, HTTP 200)
- Complete vs Cancel race handling (HTTP 409 Conflict)
- Cancel vs Complete race handling (HTTP 409 Conflict)
- Double Cancel idempotency
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fieldops.application.service_lifecycle_service import ServiceLifecycleService
from fieldops.core.exceptions import (
    AppointmentAlreadyCancelledError,
    AppointmentAlreadyCompletedError,
)
from fieldops.db.models import (
    Appointment,
    Customer,
    OutboxEvent,
    ServiceRequest,
    Technician,
)
from fieldops.main import app


def _seed_concurrency_entities(session: Session) -> tuple[Customer, Technician, ServiceRequest, Appointment]:
    """Helper fixture to seed test records for concurrency tests."""
    customer = Customer(
        name="Race Test Customer",
        email="race.customer@example.com",
        phone="+81-90-8888-9999",
    )
    session.add(customer)
    session.flush()

    technician = Technician(
        name="Field Tech Yuto",
        service_area="Tokyo-Central",
        status="active",
        max_daily_work_minutes=480,
    )
    session.add(technician)
    session.flush()

    sr = ServiceRequest(
        customer_id=customer.id,
        raw_message="Power generator overheating",
        service_type="Power Generator Maintenance",
        urgency="high",
        location="Tokyo-Central",
        status="scheduled",
    )
    session.add(sr)
    session.flush()

    now = datetime.now(timezone.utc)
    appt = Appointment(
        service_request_id=sr.id,
        technician_id=technician.id,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        status="scheduled",
    )
    session.add(appt)
    session.commit()
    session.refresh(customer)
    session.refresh(technician)
    session.refresh(sr)
    session.refresh(appt)
    return customer, technician, sr, appt


def test_double_complete_idempotency(test_db_session: Session):
    """Calling complete_service twice produces zero duplicate outbox events and returns the existing completed record."""
    _, _, sr, appt = _seed_concurrency_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    # First completion
    first_result = lifecycle.complete_service(
        appt.id,
        completion_notes="First run",
        resolution_summary="Done",
        actor_type="operator",
    )
    test_db_session.commit()
    assert first_result.status == "completed"

    outbox_count_first = (
        test_db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "appointment.completed", OutboxEvent.aggregate_id == str(appt.id))
        .count()
    )
    assert outbox_count_first == 1

    # Second completion (idempotent duplicate call)
    second_result = lifecycle.complete_service(
        appt.id,
        completion_notes="Duplicate run attempt",
        resolution_summary="Duplicate",
        actor_type="operator",
    )
    test_db_session.commit()
    assert second_result.status == "completed"

    # Verify NO additional outbox events created
    outbox_count_second = (
        test_db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "appointment.completed", OutboxEvent.aggregate_id == str(appt.id))
        .count()
    )
    assert outbox_count_second == 1, "Duplicate outbox event must not be created on second complete"


def test_complete_vs_cancel_race(test_db_session: Session):
    """When appointment has already been completed, a subsequent cancellation attempt must raise 409 Conflict."""
    _, _, _, appt = _seed_concurrency_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    # Commits completion
    lifecycle.complete_service(appt.id)
    test_db_session.commit()

    # Attempt to cancel must be rejected with 409 Conflict
    with pytest.raises(AppointmentAlreadyCompletedError):
        lifecycle.cancel_request(appointment_id=appt.id, reason="Late cancellation attempt")


def test_cancel_vs_complete_race(test_db_session: Session):
    """When appointment has already been cancelled, a subsequent complete attempt must raise 409 Conflict."""
    _, _, _, appt = _seed_concurrency_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    # Commits cancellation
    lifecycle.cancel_request(appointment_id=appt.id, reason="Customer cancelled")
    test_db_session.commit()

    # Attempt to complete must be rejected with 409 Conflict
    with pytest.raises(AppointmentAlreadyCancelledError):
        lifecycle.complete_service(appt.id, completion_notes="Should fail")


def test_double_cancel_idempotency(test_db_session: Session):
    """Calling cancel_request twice on the same appointment is safe and idempotent."""
    _, _, _, appt = _seed_concurrency_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    sr_1, appt_1 = lifecycle.cancel_request(appointment_id=appt.id, reason="First cancel")
    test_db_session.commit()
    assert appt_1.status == "cancelled"

    outbox_count_first = (
        test_db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "appointment.cancelled", OutboxEvent.aggregate_id == str(appt.id))
        .count()
    )
    assert outbox_count_first == 1

    # Second cancel call
    sr_2, appt_2 = lifecycle.cancel_request(appointment_id=appt.id, reason="Second cancel")
    test_db_session.commit()
    assert appt_2.status == "cancelled"

    outbox_count_second = (
        test_db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "appointment.cancelled", OutboxEvent.aggregate_id == str(appt.id))
        .count()
    )
    assert outbox_count_second == 1, "Duplicate outbox event must not be created on second cancel"


def test_api_complete_and_cancel_endpoints(test_db_session: Session):
    """Verify HTTP API endpoints for complete and cancel with HTTP status codes and conflict handling."""
    from tests.conftest import TEST_OPERATOR_HEADERS
    client = TestClient(app, headers=TEST_OPERATOR_HEADERS)
    _, _, _, appt = _seed_concurrency_entities(test_db_session)

    # 1. Start appointment
    start_resp = client.post(f"/appointments/{appt.id}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "in_progress"

    # 2. Complete appointment
    comp_resp = client.post(
        f"/appointments/{appt.id}/complete",
        json={
            "completion_notes": "All checks passed.",
            "resolution_summary": "Generator functional.",
        },
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "completed"

    # 3. Complete again -> 200 OK (idempotent)
    comp_resp_2 = client.post(f"/appointments/{appt.id}/complete")
    assert comp_resp_2.status_code == 200

    # 4. Attempt to cancel completed appointment -> 409 Conflict
    cancel_resp = client.post(f"/appointments/{appt.id}/cancel", json={"reason": "Late cancel"})
    assert cancel_resp.status_code == 409
