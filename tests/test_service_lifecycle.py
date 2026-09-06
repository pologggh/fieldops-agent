"""Automated tests for Phase 24 Service Lifecycle Completion.

Tests state transition rules, dual-entity synchronization, history preservation,
and role capability evaluation across the entire service lifecycle.
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from fieldops.application.service_lifecycle_service import ServiceLifecycleService
from fieldops.core.exceptions import (
    AppointmentAlreadyCancelledError,
    AppointmentAlreadyCompletedError,
    AppointmentNotReschedulableError,
    InvalidStateTransitionError,
    RequestNotCancellableError,
)
from fieldops.db.models import (
    Appointment,
    Customer,
    OutboxEvent,
    RescheduleRequest,
    ServiceRequest,
    Technician,
)


def _seed_entities(session: Session) -> tuple[Customer, Technician, ServiceRequest, Appointment]:
    """Helper fixture to seed base customer, technician, service request, and appointment."""
    customer = Customer(
        name="Lifecycle Test Customer",
        email="lifecycle.customer@example.com",
        phone="+81-90-1111-2222",
    )
    session.add(customer)
    session.flush()

    technician = Technician(
        name="Lead Tech Kenji",
        service_area="Tokyo-Shinjuku",
        status="active",
        max_daily_work_minutes=480,
    )
    session.add(technician)
    session.flush()

    sr = ServiceRequest(
        customer_id=customer.id,
        raw_message="Server room AC leaking refrigerant",
        service_type="HVAC Emergency",
        urgency="high",
        location="Tokyo-Shinjuku",
        status="scheduled",
    )
    session.add(sr)
    session.flush()

    now = datetime.now(timezone.utc)
    appt = Appointment(
        service_request_id=sr.id,
        technician_id=technician.id,
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=4),
        status="scheduled",
    )
    session.add(appt)
    session.commit()
    session.refresh(customer)
    session.refresh(technician)
    session.refresh(sr)
    session.refresh(appt)
    return customer, technician, sr, appt


def test_capabilities_computation(test_db_session: Session):
    """Verify capabilities correctly reflect allowable transitions based on role and status."""
    _, _, sr, appt = _seed_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    # 1. Scheduled status - Operator
    op_caps = lifecycle.compute_capabilities(appointment=appt, service_request=sr, role="operator")
    assert op_caps.can_start is True
    assert op_caps.can_complete is True
    assert op_caps.can_cancel is True
    assert op_caps.can_reschedule is True
    assert op_caps.can_reassign is True

    # 2. Scheduled status - Customer
    cust_caps = lifecycle.compute_capabilities(appointment=appt, service_request=sr, role="customer")
    assert cust_caps.can_start is False
    assert cust_caps.can_complete is False
    assert cust_caps.can_cancel is True
    assert cust_caps.can_reschedule is True
    assert cust_caps.can_reassign is False

    # 3. In Progress status
    appt.status = "in_progress"
    sr.status = "in_progress"
    test_db_session.commit()

    op_caps_prog = lifecycle.compute_capabilities(appointment=appt, service_request=sr, role="operator")
    assert op_caps_prog.can_start is False
    assert op_caps_prog.can_complete is True
    assert op_caps_prog.can_cancel is True
    assert op_caps_prog.can_reschedule is False
    assert op_caps_prog.can_reassign is False

    cust_caps_prog = lifecycle.compute_capabilities(appointment=appt, service_request=sr, role="customer")
    assert cust_caps_prog.can_start is False
    assert cust_caps_prog.can_complete is False
    assert cust_caps_prog.can_cancel is False  # Customer cannot cancel in-progress service
    assert cust_caps_prog.can_reschedule is False


def test_start_service_workflow(test_db_session: Session):
    """Test advancing scheduled appointment -> in_progress synchronizes SR and emits outbox event."""
    _, _, sr, appt = _seed_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    updated_appt = lifecycle.start_service(appt.id, actor_type="operator", actor_id="op-1")
    test_db_session.commit()

    assert updated_appt.status == "in_progress"
    assert updated_appt.started_at is not None

    test_db_session.refresh(sr)
    assert sr.status == "in_progress"

    # Outbox event emitted
    outbox = (
        test_db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "appointment.started", OutboxEvent.aggregate_id == str(appt.id))
        .first()
    )
    assert outbox is not None
    assert outbox.payload["appointment_id"] == appt.id


def test_complete_service_with_notes(test_db_session: Session):
    """Test completing appointment persists notes, synchronizes SR, and emits appointment.completed outbox event."""
    _, _, sr, appt = _seed_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    # Move to in_progress first
    lifecycle.start_service(appt.id)

    completed_appt = lifecycle.complete_service(
        appt.id,
        completion_notes="Replaced leaking pressure seal and tested cooling loop.",
        resolution_summary="HVAC pressure restored to normal.",
        actor_type="operator",
    )
    test_db_session.commit()

    assert completed_appt.status == "completed"
    assert completed_appt.completed_at is not None
    assert completed_appt.completion_notes == "Replaced leaking pressure seal and tested cooling loop."
    assert completed_appt.resolution_summary == "HVAC pressure restored to normal."

    test_db_session.refresh(sr)
    assert sr.status == "completed"

    outbox = (
        test_db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "appointment.completed", OutboxEvent.aggregate_id == str(appt.id))
        .first()
    )
    assert outbox is not None


def test_customer_cannot_cancel_in_progress(test_db_session: Session):
    """Ensure customer attempting to cancel an in-progress appointment raises RequestNotCancellableError."""
    _, _, _, appt = _seed_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    lifecycle.start_service(appt.id)

    with pytest.raises(RequestNotCancellableError):
        lifecycle.cancel_request(
            appointment_id=appt.id,
            reason="Customer changed mind during repair",
            actor_type="customer",
        )


def test_reassign_technician(test_db_session: Session):
    """Test reassigning an appointment to an alternate technician preserves appointment ID and emits outbox event."""
    _, tech1, sr, appt = _seed_entities(test_db_session)
    tech2 = Technician(
        name="Backup Tech Hiro",
        service_area="Tokyo-Shinjuku",
        status="active",
        max_daily_work_minutes=480,
    )
    test_db_session.add(tech2)
    test_db_session.commit()

    lifecycle = ServiceLifecycleService(test_db_session)
    reassigned = lifecycle.reassign_technician(
        appointment_id=appt.id,
        new_technician_id=tech2.id,
        reason="Tech 1 illness",
        actor_type="operator",
    )
    test_db_session.commit()

    assert reassigned.technician_id == tech2.id

    outbox = (
        test_db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "appointment.reassigned", OutboxEvent.aggregate_id == str(appt.id))
        .first()
    )
    assert outbox is not None
    assert outbox.payload["old_technician_id"] == tech1.id
    assert outbox.payload["new_technician_id"] == tech2.id


def test_reschedule_lifecycle_approval(test_db_session: Session):
    """Test end-to-end reschedule flow: request -> approve -> replacement appointment linked with historical pointer."""
    _, tech, sr, old_appt = _seed_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    # 1. Customer requests reschedule
    resched_req = lifecycle.request_reschedule(
        service_request_id=sr.id,
        preferred_time="Tomorrow morning between 9am and 11am",
        reason="Office closed today",
        requested_by_type="customer",
    )
    test_db_session.commit()

    assert resched_req.status == "pending"
    assert resched_req.appointment_id == old_appt.id
    test_db_session.refresh(sr)
    assert sr.status == "needs_rescheduling"

    # 2. Operator approves reschedule
    new_start = datetime.now(timezone.utc) + timedelta(days=1, hours=9)
    new_end = new_start + timedelta(hours=2)

    resched_req, new_appt = lifecycle.approve_reschedule(
        reschedule_request_id=resched_req.id,
        start_time=new_start,
        end_time=new_end,
        technician_id=tech.id,
        operator_id="operator-1",
        notes="Approved for requested window",
    )
    test_db_session.commit()

    assert resched_req.status == "approved"
    assert resched_req.replacement_appointment_id == new_appt.id

    # Check history preservation & pointer links
    test_db_session.refresh(old_appt)
    assert old_appt.status == "cancelled"
    assert old_appt.replaced_by_appointment_id == new_appt.id
    assert new_appt.rescheduled_from_appointment_id == old_appt.id
    assert new_appt.status == "scheduled"

    test_db_session.refresh(sr)
    assert sr.status == "scheduled"


def test_reschedule_rejection(test_db_session: Session):
    """Test rejecting reschedule reverts service request to scheduled."""
    _, _, sr, old_appt = _seed_entities(test_db_session)
    lifecycle = ServiceLifecycleService(test_db_session)

    resched_req = lifecycle.request_reschedule(
        service_request_id=sr.id,
        preferred_time="Sunday midnight",
        reason="Convenient for me",
        requested_by_type="customer",
    )
    test_db_session.commit()

    rejected_req = lifecycle.reject_reschedule(
        reschedule_request_id=resched_req.id,
        rejection_reason="No service hours on Sunday midnight.",
        operator_id="operator-1",
    )
    test_db_session.commit()

    assert rejected_req.status == "rejected"
    assert rejected_req.rejection_reason == "No service hours on Sunday midnight."

    test_db_session.refresh(sr)
    assert sr.status == "scheduled"
    test_db_session.refresh(old_appt)
    assert old_appt.status == "scheduled"
