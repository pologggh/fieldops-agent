"""Acceptance Test 3: SLA Breach, Escalation Queue, and Safe Customer Projection."""

from datetime import datetime, timedelta, timezone
from fieldops.db.models import ServiceRequest


def test_escalation_queue_and_safe_customer_projection(
    client, operator_headers, admin_headers, customer_alpha, test_db_session
):
    # Step 1: Create an emergency service request that has breached SLA deadline
    now = datetime.now(timezone.utc)
    sr = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Urgent: Freon leak detected in main datacenter server room.",
        service_type="HVAC",
        urgency="emergency",
        status="no_technician_available",
        location="Chiyoda, Tokyo",
        sla_deadline=now - timedelta(minutes=45),  # SLA breached 45 mins ago
    )
    test_db_session.add(sr)
    test_db_session.commit()
    test_db_session.refresh(sr)

    # Step 2: Operator escalations queue must flag this ticket
    esc_res = client.get("/escalations", headers=operator_headers)
    assert esc_res.status_code == 200, esc_res.text
    escalations = esc_res.json()
    escalated_ids = (
        [e["id"] for e in escalations]
        if isinstance(escalations, list)
        else [e["id"] for e in escalations.get("items", [])]
    )
    assert sr.id in escalated_ids

    # Step 3: Admin system summary reflects the open escalation / SLA breach
    summary_res = client.get("/admin/system/summary", headers=admin_headers)
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert summary["open_escalations_count"] >= 1
    assert summary["sla_breaches_count"] >= 1

    # Step 4: Customer views ticket - must see calm, safe customer projection without internal panic/breach alerts
    cust_view = client.get(
        f"/customer/requests/{sr.id}", headers=customer_alpha["headers"]
    ).json()
    status_text = cust_view["customer_status"].lower()
    assert "breach" not in status_text
    assert "panic" not in status_text
    assert "error" not in status_text
    assert "no technician" not in status_text
    assert cust_view["customer_status"] in [
        "We are reviewing your request",
        "We are reviewing alternative scheduling options.",
    ]
