"""Acceptance Test 5: Customer Cancellation and Non-Cancellable State Enforcement."""

from datetime import datetime, timedelta, timezone
from fieldops.db.models import Appointment, OutboxEvent, ServiceRequest, Technician


def test_customer_cancellation_and_non_cancellable_enforcement(
    client, operator_headers, customer_alpha, test_db_session
):
    now = datetime.now(timezone.utc)

    # --------------------------------------------------------------------------
    # Part 1: Happy Path Cancellation & Idempotency
    # --------------------------------------------------------------------------
    tech = Technician(
        name="Cancellation Tech",
        status="active",
        service_area="Tokyo",
        max_daily_jobs=5,
    )
    test_db_session.add(tech)
    test_db_session.flush()

    sr1 = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Plumbing leak in bathroom.",
        service_type="Plumbing",
        urgency="low",
        status="scheduled",
        location="Shinjuku, Tokyo",
    )
    test_db_session.add(sr1)
    test_db_session.flush()

    appt1 = Appointment(
        service_request_id=sr1.id,
        technician_id=tech.id,
        start_time=now + timedelta(days=2, hours=10),
        end_time=now + timedelta(days=2, hours=12),
        status="scheduled",
    )
    test_db_session.add(appt1)
    test_db_session.commit()

    # Customer cancels scheduled request
    cancel_res = client.post(
        f"/customer/requests/{sr1.id}/cancel",
        headers=customer_alpha["headers"],
        json={"reason": "Customer no longer needs repair."},
    )
    assert cancel_res.status_code == 200, cancel_res.text

    test_db_session.expire_all()
    test_db_session.refresh(sr1)
    test_db_session.refresh(appt1)
    assert sr1.status == "cancelled"
    assert appt1.status == "cancelled"

    # Outbox event created
    outbox_event = (
        test_db_session.query(OutboxEvent)
        .filter_by(event_type="appointment.cancelled", aggregate_id=str(appt1.id))
        .first()
    )
    assert outbox_event is not None

    # Repeated cancellation is idempotent (returns 200)
    repeat_cancel = client.post(
        f"/customer/requests/{sr1.id}/cancel",
        headers=customer_alpha["headers"],
        json={"reason": "Repeated cancellation attempt"},
    )
    assert repeat_cancel.status_code == 200, repeat_cancel.text

    # --------------------------------------------------------------------------
    # Part 2: Non-Cancellable State: In-Progress
    # --------------------------------------------------------------------------
    sr2 = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Electrical short circuit.",
        service_type="Electrical",
        urgency="high",
        status="in_progress",
        location="Shibuya, Tokyo",
    )
    test_db_session.add(sr2)
    test_db_session.flush()

    appt2 = Appointment(
        service_request_id=sr2.id,
        technician_id=tech.id,
        start_time=now,
        end_time=now + timedelta(hours=2),
        status="in_progress",
        started_at=now,
    )
    test_db_session.add(appt2)
    test_db_session.commit()

    # Customer attempts to cancel an in-progress appointment
    blocked_in_progress = client.post(
        f"/customer/requests/{sr2.id}/cancel",
        headers=customer_alpha["headers"],
        json={"reason": "Trying to cancel while technician is on site."},
    )
    assert blocked_in_progress.status_code == 409, blocked_in_progress.text
    assert "in progress" in blocked_in_progress.text.lower() or "cannot be cancelled" in blocked_in_progress.text.lower()

    # --------------------------------------------------------------------------
    # Part 3: Non-Cancellable State: Completed
    # --------------------------------------------------------------------------
    sr3 = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="AC routine filter replacement.",
        service_type="HVAC",
        urgency="low",
        status="completed",
        location="Minato, Tokyo",
    )
    test_db_session.add(sr3)
    test_db_session.flush()

    appt3 = Appointment(
        service_request_id=sr3.id,
        technician_id=tech.id,
        start_time=now - timedelta(days=1, hours=2),
        end_time=now - timedelta(days=1),
        status="completed",
        started_at=now - timedelta(days=1, hours=2),
        completed_at=now - timedelta(days=1),
    )
    test_db_session.add(appt3)
    test_db_session.commit()

    # Customer attempts to cancel completed service
    blocked_completed = client.post(
        f"/customer/requests/{sr3.id}/cancel",
        headers=customer_alpha["headers"],
        json={"reason": "Trying to cancel finished work."},
    )
    assert blocked_completed.status_code == 409, blocked_completed.text
    assert "completed" in blocked_completed.text.lower() or "cannot cancel" in blocked_completed.text.lower()
