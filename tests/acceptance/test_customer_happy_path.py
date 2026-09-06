"""Acceptance Test 1: Customer Happy Path Full End-to-End Business Flow."""

from fieldops.db.models import Appointment, AuditLog, OutboxEvent, ServiceRequest


def test_customer_happy_path_full_flow(
    client, admin_headers, operator_headers, customer_alpha, test_db_session
):
    # Step 1: Admin configures active technician
    tech_res = client.post(
        "/admin/technicians",
        headers=admin_headers,
        json={
            "name": "Ken Sato",
            "service_area": "Shinjuku",
            "status": "active",
            "max_daily_work_minutes": 480,
            "max_daily_jobs": 5,
            "skills": ["HVAC"],
        },
    )
    assert tech_res.status_code == 201, tech_res.text
    tech_id = tech_res.json()["id"]

    # Step 2: Customer Alpha initiates conversation and submits maintenance requirement
    conv_start = client.post(
        "/customer/conversations",
        headers=customer_alpha["headers"],
        json={"initial_message": "Central AC leaking water and blowing hot air at 123 Main Street in Shinjuku, need technician tomorrow afternoon."},
    )
    assert conv_start.status_code == 201, conv_start.text
    conv_data = conv_start.json()
    conv_id = conv_data["id"]
    assert conv_data["draft"]["is_complete"] is True
    assert conv_data["draft"]["service_type"] == "HVAC"
    assert conv_data["draft"]["location"] == "Shinjuku"

    # Step 3: Customer reviews draft and confirms submission
    confirm_res = client.post(
        f"/customer/conversations/{conv_id}/confirm",
        headers=customer_alpha["headers"],
    )
    assert confirm_res.status_code in (200, 201), confirm_res.text
    sr_id = confirm_res.json()["service_request_id"]
    assert sr_id is not None

    # Verify ServiceRequest in database
    sr = test_db_session.query(ServiceRequest).filter_by(id=sr_id).first()
    assert sr is not None
    assert sr.customer_id == customer_alpha["id"]
    assert sr.location == "Shinjuku"
    assert sr.service_type == "HVAC"

    # Step 4: Operator reviews and approves proposal
    approve_res = client.post(
        f"/service-requests/{sr_id}/approval",
        headers=operator_headers,
        json={
            "decision": "approve",
            "technician_id": tech_id,
            "start_time": "2026-09-10T14:00:00+09:00",
            "end_time": "2026-09-10T16:00:00+09:00",
            "notes": "Approved for Ken Sato",
        },
    )
    assert approve_res.status_code == 200, approve_res.text

    # Step 5: Verify Appointment created and scheduled
    appt = test_db_session.query(Appointment).filter_by(service_request_id=sr_id).first()
    assert appt is not None
    assert appt.technician_id == tech_id
    assert appt.status == "scheduled"

    # Step 6: Technician Check-In (Start service)
    start_res = client.post(
        f"/appointments/{appt.id}/start",
        headers=operator_headers,
    )
    assert start_res.status_code == 200, start_res.text
    assert start_res.json()["status"] == "in_progress"
    assert start_res.json()["started_at"] is not None

    # Step 7: Technician Completes Job
    complete_res = client.post(
        f"/appointments/{appt.id}/complete",
        headers=operator_headers,
        json={
            "completion_notes": "Replaced clogged condensation drain pipe and recharged refrigerant.",
            "resolution_summary": "HVAC unit operating at normal cooling efficiency.",
        },
    )
    assert complete_res.status_code == 200, complete_res.text
    assert complete_res.json()["status"] == "completed"

    # Step 8: Verify ServiceRequest and Appointment final state
    test_db_session.expire_all()
    sr_final = test_db_session.query(ServiceRequest).filter_by(id=sr_id).first()
    assert sr_final.status == "completed"

    # Verify AuditLog has recorded state transitions
    audit_entries = test_db_session.query(AuditLog).filter_by(entity_type="service_request", entity_id=str(sr_id)).all()
    assert len(audit_entries) > 0
