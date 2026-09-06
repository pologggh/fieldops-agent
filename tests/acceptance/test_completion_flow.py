"""Acceptance Test 6: Appointment Completion Flow and Double-Complete Idempotency."""

from datetime import datetime, timedelta, timezone
from fieldops.db.models import Appointment, OutboxEvent, ServiceRequest, Technician


def test_appointment_completion_lifecycle_and_idempotency(
    client, operator_headers, customer_alpha, test_db_session
):
    now = datetime.now(timezone.utc)

    # Step 1: Create technician, service request, and scheduled appointment
    tech = Technician(
        name="Field Technician Alice",
        status="active",
        service_area="Tokyo",
        max_daily_jobs=5,
    )
    test_db_session.add(tech)
    test_db_session.flush()

    sr = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Main network router offline in office.",
        service_type="Networking",
        urgency="medium",
        status="scheduled",
        location="Shinagawa, Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    appt = Appointment(
        service_request_id=sr.id,
        technician_id=tech.id,
        start_time=now,
        end_time=now + timedelta(hours=2),
        status="scheduled",
    )
    test_db_session.add(appt)
    test_db_session.commit()

    # Step 2: Start Service (Check-in)
    start_res = client.post(f"/appointments/{appt.id}/start", headers=operator_headers)
    assert start_res.status_code == 200, start_res.text
    assert start_res.json()["status"] == "in_progress"

    test_db_session.expire_all()
    test_db_session.refresh(appt)
    test_db_session.refresh(sr)
    assert appt.status == "in_progress"
    assert appt.started_at is not None
    assert sr.status == "in_progress"

    # Step 3: Complete Service
    complete_res = client.post(
        f"/appointments/{appt.id}/complete",
        headers=operator_headers,
        json={
            "completion_notes": "Replaced blown power supply module on central switch.",
            "resolution_summary": "All network links operational, 1Gbps ping verified.",
        },
    )
    assert complete_res.status_code == 200, complete_res.text
    comp_data = complete_res.json()
    assert comp_data["status"] == "completed"

    test_db_session.expire_all()
    test_db_session.refresh(appt)
    test_db_session.refresh(sr)
    assert appt.status == "completed"
    assert appt.completed_at is not None
    assert appt.completion_notes == "Replaced blown power supply module on central switch."
    assert sr.status == "completed"

    # Verify Outbox event created for follow-up notification
    outbox_count_first = (
        test_db_session.query(OutboxEvent)
        .filter_by(event_type="appointment.completed", aggregate_id=str(appt.id))
        .count()
    )
    assert outbox_count_first >= 1

    # Step 4: Double-Complete Idempotency Check
    # Calling complete on an already completed appointment must return 200 without throwing errors
    repeat_complete = client.post(
        f"/appointments/{appt.id}/complete",
        headers=operator_headers,
        json={
            "completion_notes": "Duplicate complete attempt.",
        },
    )
    assert repeat_complete.status_code == 200, repeat_complete.text

    test_db_session.expire_all()
    test_db_session.refresh(appt)
    assert appt.status == "completed"
    # Original completion notes preserved
    assert appt.completion_notes == "Replaced blown power supply module on central switch."
