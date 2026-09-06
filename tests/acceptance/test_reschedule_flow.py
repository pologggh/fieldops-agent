"""Acceptance Test 4: Customer Reschedule Lifecycle Flow."""

from datetime import datetime, timedelta, timezone
from fieldops.db.models import Appointment, ServiceRequest, Technician


def test_customer_reschedule_lifecycle(
    client, operator_headers, customer_alpha, test_db_session
):
    # Step 1: Create active technician
    tech = Technician(
        name="Reschedule Tech Joe",
        status="active",
        service_area="Tokyo",
        max_daily_jobs=5,
    )
    test_db_session.add(tech)
    test_db_session.flush()

    # Step 2: Create ServiceRequest with active appointment
    now = datetime.now(timezone.utc)
    sr = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Check commercial refrigerator condenser.",
        service_type="Appliance Repair",
        urgency="low",
        status="approved",
        location="Shibuya, Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    appt1 = Appointment(
        service_request_id=sr.id,
        technician_id=tech.id,
        start_time=now + timedelta(days=2, hours=10),
        end_time=now + timedelta(days=2, hours=12),
        status="scheduled",
    )
    test_db_session.add(appt1)
    test_db_session.commit()

    # Step 3: Customer requests reschedule
    resched_res = client.post(
        f"/customer/requests/{sr.id}/reschedule",
        headers=customer_alpha["headers"],
        json={
            "preferred_time": "Friday 3:00 PM",
            "reason": "Building maintenance conflict, need later time.",
        },
    )
    assert resched_res.status_code == 200, resched_res.text
    test_db_session.refresh(sr)
    assert sr.status == "needs_rescheduling"

    # Step 4: Operator approves new slot
    new_start = now + timedelta(days=5, hours=15)
    new_end = now + timedelta(days=5, hours=17)
    approval_res = client.post(
        f"/service-requests/{sr.id}/approval",
        headers=operator_headers,
        json={
            "decision": "approve",
            "technician_id": tech.id,
            "start_time": new_start.isoformat(),
            "end_time": new_end.isoformat(),
            "notes": "Reschedule approved by dispatch.",
        },
    )
    assert approval_res.status_code == 200, approval_res.text

    # Step 5: Verify Old appointment is superseded and new appointment is active
    test_db_session.expire_all()
    test_db_session.refresh(appt1)
    assert appt1.status in ("cancelled", "rescheduled")

    appts = test_db_session.query(Appointment).filter_by(service_request_id=sr.id).all()
    assert len(appts) == 2
    active_appts = [a for a in appts if a.status == "scheduled"]
    assert len(active_appts) == 1
    assert active_appts[0].id != appt1.id

    # Step 6: Customer views refreshed active appointment in portal
    cust_view = client.get(
        f"/customer/requests/{sr.id}", headers=customer_alpha["headers"]
    ).json()
    assert cust_view["customer_status"] == "Appointment scheduled"
    assert cust_view["appointment"]["id"] == active_appts[0].id
