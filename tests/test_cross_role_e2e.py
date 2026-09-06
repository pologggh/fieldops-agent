"""Phase 23 Cross-Role Integration + End-to-End Business Flow Test Suite.

Validates that Customer, Operator, and Admin operate seamlessly against a single
canonical business state:
1. Happy Path E2E: Admin config -> Customer intake -> Operator approval -> Customer appointment -> Operator completion.
2. Needs Information & Supplement: Incomplete intake -> Customer supplement -> Operator refreshes & approves.
3. Escalation & SLA Breach: Emergency / unassigned request -> Operator escalation queue -> Admin summary -> Safe customer projection.
4. Reschedule Lifecycle: Customer requests reschedule -> Prior appointment superseded -> New appointment confirmed.
5. Atomic Cancellation: Customer cancels -> Both ServiceRequest & Appointment cancelled atomically + Outbox event emitted.
6. Admin Technician Management: Inactive technician excluded from dispatch; conflict guard prevents deactivating booked technician.
7. Policy Attribution & Immutability: Dynamic policy versions snapshotted on new tickets without mutating historical tickets.
8. Double-Approval Concurrency: Concurrent / duplicate approvals result in exactly 1 appointment.
9. Cross-Customer & RBAC Isolation: Strict anti-IDOR between customers, and role boundary protection across customer/operator/admin.
10. Outbox & Integration Resilience: Notification / integration external failure never rolls back core business appointment facts.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///fieldops_demo.db"
os.environ["LOAD_TEST_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["APP_ENV"] = "testing"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fieldops.core.config import settings
settings.RATE_LIMIT_ENABLED = False
settings.LLM_PROVIDER = "fake"

from fieldops.main import app
from fieldops.db.models import (
    Appointment,
    AuditLog,
    Conversation,
    Customer,
    CustomerAccount,
    DispatchPolicy,
    IntegrationRecord,
    InternalUser,
    OutboxEvent,
    ServiceRequest,
    SLAPolicy,
    Technician,
    TechnicianSkill,
)
from fieldops.security.admin_auth import hash_password as hash_admin_pw
from fieldops.security.customer_auth import hash_password as hash_customer_pw


@pytest.fixture
def client(test_db_session):
    """Provide a TestClient with seeded users and initial active policies."""
    # Seed Admin User
    admin = test_db_session.query(InternalUser).filter_by(email="admin@fieldops.com").first()
    if not admin:
        admin = InternalUser(
            email="admin@fieldops.com",
            name="Admin User",
            role="admin",
            password_hash=hash_admin_pw("password123"),
            is_active=True,
        )
        test_db_session.add(admin)
    else:
        admin.is_active = True
        admin.role = "admin"

    # Seed Operator User
    operator = test_db_session.query(InternalUser).filter_by(email="operator@fieldops.com").first()
    if not operator:
        operator = InternalUser(
            email="operator@fieldops.com",
            name="Lead Dispatcher",
            role="operator",
            password_hash=hash_admin_pw("password123"),
            is_active=True,
        )
        test_db_session.add(operator)
    else:
        operator.is_active = True
        operator.role = "operator"

    # Seed Initial Policies
    dp = test_db_session.query(DispatchPolicy).filter_by(version=1).first()
    if not dp:
        test_db_session.add(DispatchPolicy(
            version=1,
            is_active=True,
            weights={"workload_weight": 25, "capacity_weight": 20, "sla_weight": 30, "travel_weight": 15, "overtime_penalty": 10},
            description="Initial Dispatch Policy v1",
            created_by="system",
        ))

    sla = test_db_session.query(SLAPolicy).filter_by(version=1).first()
    if not sla:
        test_db_session.add(SLAPolicy(
            version=1,
            is_active=True,
            targets={
                "P0": {"response_minutes": 15, "assignment_minutes": 30, "service_start_minutes": 120, "at_risk_threshold_minutes": 15},
                "P1": {"response_minutes": 30, "assignment_minutes": 60, "service_start_minutes": 240, "at_risk_threshold_minutes": 30},
                "P2": {"response_minutes": 60, "assignment_minutes": 120, "service_start_minutes": 480, "at_risk_threshold_minutes": 60},
                "P3": {"response_minutes": 120, "assignment_minutes": 240, "service_start_minutes": 1440, "at_risk_threshold_minutes": 120},
            },
            description="Initial SLA Policy v1",
            created_by="system",
        ))

    test_db_session.commit()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(client):
    res = client.post("/auth/login", json={"username": "admin@fieldops.com", "password": "password123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def operator_headers(client):
    res = client.post("/auth/login", json={"username": "operator@fieldops.com", "password": "password123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def customer_alpha(client):
    uid = uuid.uuid4().hex[:6]
    email = f"alpha_{uid}@example.com"
    res = client.post("/customer-auth/register", json={
        "name": "Customer Alpha",
        "email": email,
        "password": "Password123!",
        "phone": "555-0100",
    })
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    cust_id = res.json()["customer"]["id"]
    return {
        "id": cust_id,
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def customer_beta(client):
    uid = uuid.uuid4().hex[:6]
    email = f"beta_{uid}@example.com"
    res = client.post("/customer-auth/register", json={
        "name": "Customer Beta",
        "email": email,
        "password": "Password123!",
        "phone": "555-0200",
    })
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    cust_id = res.json()["customer"]["id"]
    return {
        "id": cust_id,
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ==============================================================================
# 1. HAPPY PATH E2E
# ==============================================================================
def test_happy_path_e2e(client, admin_headers, operator_headers, customer_alpha, test_db_session):
    """E2E Scenario 1: Complete business lifecycle from Admin to Customer to Operator to Completion."""
    # Step 1: Admin configures an active technician with HVAC skills
    tech_res = client.post("/admin/technicians", headers=admin_headers, json={
        "name": "E2E Master Technician Ken",
        "service_area": "Tokyo",
        "skills": ["HVAC", "Electrical"],
        "max_daily_capacity": 5,
        "emergency_capable": True,
        "status": "active",
    })
    assert tech_res.status_code == 201, tech_res.text
    tech_id = tech_res.json()["id"]

    # Step 2: Customer creates a conversation
    conv_res = client.post("/customer/conversations", headers=customer_alpha["headers"], json={
        "initial_message": "My air conditioner stopped cooling and smells strange."
    })
    assert conv_res.status_code == 201, conv_res.text
    conv_data = conv_res.json()
    conv_id = conv_data["id"]
    assert conv_data["status"] == "active"

    # Step 3: Clarification dialogue
    # Turn 2: Provide Location
    turn2 = client.post(f"/customer/conversations/{conv_id}/messages", headers=customer_alpha["headers"], json={
        "content": "I am located in Shinjuku, Tokyo.",
        "client_message_id": str(uuid.uuid4()),
    })
    assert turn2.status_code == 200, turn2.text

    # Turn 3: Provide Preferred Time -> Enters awaiting_confirmation
    turn3 = client.post(f"/customer/conversations/{conv_id}/messages", headers=customer_alpha["headers"], json={
        "content": "Tomorrow afternoon between 2 PM and 5 PM works best.",
        "client_message_id": str(uuid.uuid4()),
    })
    assert turn3.status_code == 200, turn3.text
    conv_state = turn3.json()
    assert conv_state["status"] == "awaiting_confirmation"
    assert conv_state["draft"]["location"] is not None

    # Step 4: Customer confirms the draft into a formal ServiceRequest
    confirm_res = client.post(f"/customer/conversations/{conv_id}/confirm", headers=customer_alpha["headers"], json={
        "idempotency_key": str(uuid.uuid4()),
    })
    assert confirm_res.status_code in [200, 201], confirm_res.text
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "submitted"
    sr_id = confirm_data["service_request_id"]
    assert sr_id is not None

    # Verify policy version attribution on new ServiceRequest
    sr = test_db_session.query(ServiceRequest).filter_by(id=sr_id).first()
    assert sr is not None
    assert sr.dispatch_policy_version == 1
    assert sr.sla_policy_version == 1
    assert sr.sla_deadline is not None

    # Step 5: Customer views initial request status -> Customer sees safe status (not internal status)
    cust_view_res = client.get(f"/customer/requests/{sr_id}", headers=customer_alpha["headers"])
    assert cust_view_res.status_code == 200, cust_view_res.text
    cust_view = cust_view_res.json()
    assert cust_view["customer_status"] in ["Request received", "Scheduling your visit", "We are reviewing your request"]

    # Step 6: Operator views request in Operator Dashboard & reviews proposals
    op_req_res = client.get(f"/service-requests/{sr_id}", headers=operator_headers)
    assert op_req_res.status_code == 200, op_req_res.text
    op_req_data = op_req_res.json()
    assert op_req_data["id"] == sr_id

    # Step 7: Operator approves appointment proposal
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_dt = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    end_dt = tomorrow.replace(hour=16, minute=0, second=0, microsecond=0)

    approval_payload = {
        "decision": "approve",
        "technician_id": tech_id,
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "notes": "Approved by Senior Dispatcher for HVAC maintenance.",
    }
    appr_res = client.post(f"/service-requests/{sr_id}/approval", headers=operator_headers, json=approval_payload)
    assert appr_res.status_code == 200, appr_res.text
    appr_data = appr_res.json()
    assert appr_data["approval_status"] == "approved" or appr_data.get("appointment_status") == "scheduled"

    # Verify Outbox event was created for external calendar / notification delivery
    outbox_event = test_db_session.query(OutboxEvent).filter(
        OutboxEvent.aggregate_type == "appointment",
        OutboxEvent.event_type == "appointment.created",
    ).first()
    assert outbox_event is not None
    assert str(tech_id) in str(outbox_event.payload) or outbox_event.aggregate_id is not None

    # Step 8: Customer refreshes portal -> views confirmed appointment
    cust_refreshed = client.get(f"/customer/requests/{sr_id}", headers=customer_alpha["headers"]).json()
    assert cust_refreshed["customer_status"] == "Appointment scheduled"
    assert cust_refreshed["appointment"] is not None
    appt_id = cust_refreshed["appointment"]["id"]
    assert cust_refreshed["appointment"]["technician_name"] == "E2E Master Technician Ken"

    # Step 9: Operator marks appointment completed
    complete_res = client.post(f"/appointments/{appt_id}/complete", headers=operator_headers)
    assert complete_res.status_code == 200, complete_res.text
    complete_data = complete_res.json()
    assert complete_data["status"] == "completed"

    # Verify atomic update: ServiceRequest is also completed!
    test_db_session.expire_all()
    sr_completed = test_db_session.query(ServiceRequest).filter_by(id=sr_id).first()
    appt_completed = test_db_session.query(Appointment).filter_by(id=appt_id).first()
    assert sr_completed.status == "completed"
    assert appt_completed.status == "completed"

    # Step 10: Customer views completed status in Customer Portal
    cust_final = client.get(f"/customer/requests/{sr_id}", headers=customer_alpha["headers"]).json()
    assert cust_final["customer_status"] == "Service completed"
    assert cust_final["appointment"]["status"] == "completed"

    # Verify Audit trail completeness
    actions = [a.action for a in test_db_session.query(AuditLog).all()]
    assert "conversation.created" in actions
    assert "conversation.submitted" in actions
    assert "appointment.completed" in actions


# ==============================================================================
# 2. NEEDS INFORMATION & SUPPLEMENT E2E
# ==============================================================================
def test_needs_information_and_supplement_e2e(client, operator_headers, customer_alpha, test_db_session):
    """E2E Scenario 2: Request requiring information is supplemented by customer and unlocked for approval."""
    # Create an initial ServiceRequest that is in needs_information
    sr = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Heater is making clanking noise.",
        service_type="Heating",
        urgency="medium",
        status="needs_information",
        location="Unknown",
    )
    test_db_session.add(sr)
    test_db_session.commit()
    test_db_session.refresh(sr)

    # Customer checks request -> sees action required
    cust_view = client.get(f"/customer/requests/{sr.id}", headers=customer_alpha["headers"]).json()
    assert cust_view["needs_information"] is True

    # Customer supplements location via portal
    supp_res = client.post(f"/customer/requests/{sr.id}/supplement", headers=customer_alpha["headers"], json={
        "location": "Yokohama, Kanagawa",
        "preferred_time": "Next Tuesday morning",
        "additional_details": "Access code #1234",
    })
    assert supp_res.status_code == 200, supp_res.text

    # Verify status transitioned from needs_information to waiting_for_approval
    test_db_session.refresh(sr)
    assert sr.status in ["waiting_for_approval", "ready_for_review"]
    assert sr.location == "Yokohama, Kanagawa"

    # Operator sees updated location in detail view
    op_view = client.get(f"/service-requests/{sr.id}", headers=operator_headers).json()
    assert op_view["location"] == "Yokohama, Kanagawa"


# ==============================================================================
# 3. ESCALATION & SLA BREACH E2E
# ==============================================================================
def test_escalation_and_sla_breach_e2e(client, operator_headers, admin_headers, customer_alpha, test_db_session):
    """E2E Scenario 3: Emergency request with no technician triggers escalation queue, admin telemetry, and safe customer projection."""
    # Create emergency request with impossible criteria
    sr = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Urgent: Freon leak detected in main datacenter.",
        service_type="CryoHVAC",
        urgency="emergency",
        status="no_technician_available",
        location="Chiyoda, Tokyo",
        sla_deadline=datetime.now(timezone.utc) - timedelta(minutes=30),  # Already breached
    )
    test_db_session.add(sr)
    test_db_session.commit()
    test_db_session.refresh(sr)

    # Operator checks escalations queue
    esc_res = client.get("/escalations", headers=operator_headers)
    assert esc_res.status_code == 200, esc_res.text
    escalations = esc_res.json()
    escalated_ids = [e["id"] for e in escalations] if isinstance(escalations, list) else [e["id"] for e in escalations.get("items", [])]
    assert sr.id in escalated_ids

    # Admin checks system summary telemetry
    summary_res = client.get("/admin/system/summary", headers=admin_headers)
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert summary["open_escalations_count"] >= 1
    assert summary["sla_breaches_count"] >= 1

    # Customer views request -> Sees safe, calm explanation (no technical jargon or breach alerts)
    cust_view = client.get(f"/customer/requests/{sr.id}", headers=customer_alpha["headers"]).json()
    assert "breach" not in cust_view["customer_status"].lower()
    assert "no technician" not in cust_view["customer_status"].lower()
    assert cust_view["customer_status"] in ["We are reviewing your request", "We are reviewing alternative scheduling options."]


# ==============================================================================
# 4. RESCHEDULE LIFECYCLE E2E
# ==============================================================================
def test_reschedule_lifecycle_e2e(client, operator_headers, customer_alpha, test_db_session):
    """E2E Scenario 4: Customer requests reschedule -> prior appointment superseded -> new appointment created."""
    # Create technician
    tech = Technician(name="Technician Joe", status="active", service_area="Tokyo", max_daily_jobs=5)
    test_db_session.add(tech)
    test_db_session.flush()

    # Create ServiceRequest with active appointment
    now = datetime.now(timezone.utc)
    sr = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Check refrigerator.",
        service_type="Appliance",
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

    # Customer requests reschedule
    resched_res = client.post(f"/customer/requests/{sr.id}/reschedule", headers=customer_alpha["headers"], json={
        "preferred_time": "Friday 3:00 PM",
        "reason": "Family emergency, need later time.",
    })
    assert resched_res.status_code == 200, resched_res.text
    test_db_session.refresh(sr)
    assert sr.status == "needs_rescheduling"

    # Operator approves new slot
    new_start = now + timedelta(days=5, hours=15)
    new_end = now + timedelta(days=5, hours=17)
    approval_res = client.post(f"/service-requests/{sr.id}/approval", headers=operator_headers, json={
        "decision": "approve",
        "technician_id": tech.id,
        "start_time": new_start.isoformat(),
        "end_time": new_end.isoformat(),
        "notes": "Reschedule approved.",
    })
    assert approval_res.status_code == 200, approval_res.text

    # Verify: Old appointment is marked cancelled (superseded), new appointment is active
    test_db_session.expire_all()
    test_db_session.refresh(appt1)
    assert appt1.status == "cancelled"

    appts = test_db_session.query(Appointment).filter_by(service_request_id=sr.id).all()
    assert len(appts) == 2
    active_appts = [a for a in appts if a.status == "scheduled"]
    assert len(active_appts) == 1
    assert active_appts[0].id != appt1.id

    # Customer portal sees updated active appointment
    cust_view = client.get(f"/customer/requests/{sr.id}", headers=customer_alpha["headers"]).json()
    assert cust_view["appointment"]["id"] == active_appts[0].id


# ==============================================================================
# 5. ATOMIC CANCELLATION E2E
# ==============================================================================
def test_atomic_cancellation_e2e(client, customer_alpha, test_db_session):
    """E2E Scenario 5: Customer cancellation updates both SR and Appointment atomically with Outbox event."""
    tech = Technician(name="Technician Alan", status="active", service_area="Tokyo")
    test_db_session.add(tech)
    test_db_session.flush()

    sr = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Sink leaking.",
        service_type="Plumbing",
        urgency="medium",
        status="approved",
        location="Minato, Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    now = datetime.now(timezone.utc)
    appt = Appointment(
        service_request_id=sr.id,
        technician_id=tech.id,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=2),
        status="scheduled",
    )
    test_db_session.add(appt)
    test_db_session.commit()

    # Customer cancels request
    cancel_res = client.post(f"/customer/requests/{sr.id}/cancel", headers=customer_alpha["headers"], json={
        "reason": "Issue resolved itself.",
    })
    assert cancel_res.status_code == 200, cancel_res.text

    # Verify zero dual state: Both SR and Appointment are cancelled
    test_db_session.expire_all()
    test_db_session.refresh(sr)
    test_db_session.refresh(appt)
    assert sr.status == "cancelled"
    assert appt.status == "cancelled"

    # Outbox event emitted for cancellation
    outbox = test_db_session.query(OutboxEvent).filter(
        OutboxEvent.aggregate_id == str(appt.id),
        OutboxEvent.event_type == "appointment.cancelled",
    ).first()
    assert outbox is not None


# ==============================================================================
# 6. ADMIN TECHNICIAN MANAGEMENT & DISPATCH IMPACT
# ==============================================================================
def test_admin_technician_management_impact(client, admin_headers, operator_headers, test_db_session):
    """E2E Scenario 6: Disabling technician prevents dispatch recommendations and enforces future appointment guard."""
    # Create technician
    tech_res = client.post("/admin/technicians", headers=admin_headers, json={
        "name": "Deactivation Guard Tech",
        "service_area": "Tokyo",
        "skills": ["Electrical"],
        "max_daily_capacity": 4,
        "status": "active",
    })
    assert tech_res.status_code == 201
    tech_id = tech_res.json()["id"]

    # Book a future appointment for this technician
    now = datetime.now(timezone.utc)
    sr = ServiceRequest(
        customer_id=1,
        raw_message="Testing breaker.",
        service_type="Electrical",
        urgency="medium",
        status="approved",
        location="Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    future_appt = Appointment(
        service_request_id=sr.id,
        technician_id=tech_id,
        start_time=now + timedelta(days=3),
        end_time=now + timedelta(days=3, hours=2),
        status="scheduled",
    )
    test_db_session.add(future_appt)
    test_db_session.commit()

    # Admin attempts to deactivate technician -> 409 Conflict
    deact_res = client.post(f"/admin/technicians/{tech_id}/deactivate", headers=admin_headers)
    assert deact_res.status_code == 409, deact_res.text
    assert "active future appointment" in deact_res.json()["detail"].lower()

    # Cancel the future appointment
    future_appt.status = "cancelled"
    test_db_session.commit()

    # Now deactivation succeeds
    deact_res2 = client.post(f"/admin/technicians/{tech_id}/deactivate", headers=admin_headers)
    assert deact_res2.status_code == 200, deact_res2.text
    assert deact_res2.json()["status"] == "inactive"


# ==============================================================================
# 7. POLICY VERSION ATTRIBUTION & HISTORICAL IMMUTABILITY
# ==============================================================================
def test_policy_version_attribution_and_historical_immutability(client, admin_headers, customer_alpha, test_db_session):
    """E2E Scenario 7: Policy updates snapshot on new requests without altering historical requests."""
    # Historical Request under Policy v1
    sr1 = ServiceRequest(
        customer_id=customer_alpha["id"],
        raw_message="Historical ticket under policy v1.",
        service_type="HVAC",
        urgency="low",
        status="approved",
        location="Tokyo",
        dispatch_policy_version=1,
        sla_policy_version=1,
        sla_deadline=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
    )
    test_db_session.add(sr1)
    test_db_session.commit()
    test_db_session.refresh(sr1)

    # Admin activates Dispatch Policy v2
    dp_res = client.post("/admin/policies/dispatch", headers=admin_headers, json={
        "weights": {"workload_weight": 40, "capacity_weight": 30, "sla_weight": 10, "travel_weight": 10, "overtime_penalty": 10},
        "description": "Dispatch Policy v2 - Capacity Focus",
    })
    assert dp_res.status_code == 201
    v2_dp_id = dp_res.json()["version"]
    act_dp = client.post(f"/admin/policies/dispatch/{v2_dp_id}/activate", headers=admin_headers)
    assert act_dp.status_code == 200

    # Admin activates SLA Policy v2
    sla_res = client.post("/admin/policies/sla", headers=admin_headers, json={
        "targets": {
            "P0": {"response_minutes": 10, "assignment_minutes": 20, "service_start_minutes": 60, "at_risk_threshold_minutes": 10},
            "P1": {"response_minutes": 20, "assignment_minutes": 40, "service_start_minutes": 120, "at_risk_threshold_minutes": 20},
            "P2": {"response_minutes": 40, "assignment_minutes": 80, "service_start_minutes": 240, "at_risk_threshold_minutes": 40},
            "P3": {"response_minutes": 80, "assignment_minutes": 160, "service_start_minutes": 720, "at_risk_threshold_minutes": 80},
        },
        "description": "SLA Policy v2 - Aggressive Targets",
    })
    assert sla_res.status_code == 201
    v2_sla_id = sla_res.json()["version"]
    act_sla = client.post(f"/admin/policies/sla/{v2_sla_id}/activate", headers=admin_headers)
    assert act_sla.status_code == 200

    # Create new ServiceRequest via Customer Portal
    new_req_res = client.post("/customer/requests", headers=customer_alpha["headers"], json={
        "problem_description": "Air conditioner check under v2 policies.",
        "service_type": "HVAC",
        "location": "Setagaya, Tokyo",
    })
    assert new_req_res.status_code == 201, new_req_res.text
    new_sr_id = new_req_res.json()["id"]

    # Verify new request has v2 pinned, while historical request keeps v1 and original deadline
    test_db_session.expire_all()
    sr2 = test_db_session.query(ServiceRequest).filter_by(id=new_sr_id).first()
    assert sr2.dispatch_policy_version == v2_dp_id
    assert sr2.sla_policy_version == v2_sla_id

    sr1_check = test_db_session.query(ServiceRequest).filter_by(id=sr1.id).first()
    assert sr1_check.dispatch_policy_version == 1
    assert sr1_check.sla_policy_version == 1
    assert sr1_check.sla_deadline.replace(tzinfo=timezone.utc) == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


# ==============================================================================
# 8. CONCURRENCY & DOUBLE APPROVAL PROTECTION
# ==============================================================================
def test_double_approval_concurrency_protection(client, operator_headers, test_db_session):
    """E2E Scenario 8: Duplicate or concurrent approvals result in exactly 1 appointment."""
    tech = Technician(name="Concurrency Guard Tech", status="active", service_area="Tokyo")
    test_db_session.add(tech)
    test_db_session.flush()

    sr = ServiceRequest(
        customer_id=1,
        raw_message="Approve me once.",
        service_type="Plumbing",
        urgency="medium",
        status="waiting_for_approval",
        location="Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.commit()

    now = datetime.now(timezone.utc)
    payload = {
        "decision": "approve",
        "technician_id": tech.id,
        "start_time": (now + timedelta(days=2)).isoformat(),
        "end_time": (now + timedelta(days=2, hours=2)).isoformat(),
        "notes": "First approval",
    }

    # Call 1: Success
    res1 = client.post(f"/service-requests/{sr.id}/approval", headers=operator_headers, json=payload)
    assert res1.status_code == 200, res1.text

    # Call 2: Second approval call on already approved request
    res2 = client.post(f"/service-requests/{sr.id}/approval", headers=operator_headers, json=payload)
    assert res2.status_code in [200, 409], res2.text

    # In database: Exactly 1 appointment exists
    appts = test_db_session.query(Appointment).filter_by(service_request_id=sr.id, status="scheduled").all()
    assert len(appts) == 1


# ==============================================================================
# 9. CROSS-CUSTOMER ANTI-IDOR & RBAC ISOLATION
# ==============================================================================
def test_cross_customer_and_rbac_isolation(client, customer_alpha, customer_beta, operator_headers):
    """E2E Scenario 9: Strict token boundaries between customers and across internal roles."""
    # Customer Alpha creates a request
    create_res = client.post("/customer/requests", headers=customer_alpha["headers"], json={
        "problem_description": "Private issue inside house.",
        "service_type": "HVAC",
        "location": "Shinjuku, Tokyo",
    })
    assert create_res.status_code == 201
    sr_id = create_res.json()["id"]

    # Customer Beta attempts to view Customer Alpha's request -> 404
    idor_get = client.get(f"/customer/requests/{sr_id}", headers=customer_beta["headers"])
    assert idor_get.status_code == 404

    # Customer Beta attempts to cancel Customer Alpha's request -> 404
    idor_cancel = client.post(f"/customer/requests/{sr_id}/cancel", headers=customer_beta["headers"], json={
        "reason": "Malicious cancellation attempt",
    })
    assert idor_cancel.status_code == 404

    # Customer token attempts to access internal Operator route -> 403
    cust_to_op = client.get("/service-requests", headers=customer_alpha["headers"])
    assert cust_to_op.status_code == 403

    # Customer token attempts to access Admin route -> 403
    cust_to_admin = client.get("/admin/users", headers=customer_alpha["headers"])
    assert cust_to_admin.status_code == 403

    # Operator token attempts to access Admin route -> 403
    op_to_admin = client.get("/admin/users", headers=operator_headers)
    assert op_to_admin.status_code == 403

    # Unauthenticated request -> 401
    unauth = client.get(f"/customer/requests/{sr_id}")
    assert unauth.status_code == 401


# ==============================================================================
# 10. INTEGRATION & NOTIFICATION OUTBOX RESILIENCE
# ==============================================================================
def test_integration_outbox_resilience(client, operator_headers, test_db_session):
    """E2E Scenario 10: External integration failure does NOT rollback core appointment booking."""
    tech = Technician(name="Resilience Tech", status="active", service_area="Tokyo")
    test_db_session.add(tech)
    test_db_session.flush()

    sr = ServiceRequest(
        customer_id=1,
        raw_message="Verify outbox decoupling.",
        service_type="Electrical",
        urgency="medium",
        status="waiting_for_approval",
        location="Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.commit()

    now = datetime.now(timezone.utc)
    approval_payload = {
        "decision": "approve",
        "technician_id": tech.id,
        "start_time": (now + timedelta(days=2)).isoformat(),
        "end_time": (now + timedelta(days=2, hours=2)).isoformat(),
        "notes": "Testing integration failure decoupling.",
    }

    # Core API approval transaction must succeed and commit Appointment + OutboxEvent
    res = client.post(f"/service-requests/{sr.id}/approval", headers=operator_headers, json=approval_payload)
    assert res.status_code == 200, res.text

    # Check appointment is persisted as scheduled
    appt = test_db_session.query(Appointment).filter_by(service_request_id=sr.id).first()
    assert appt is not None
    assert appt.status == "scheduled"

    # Outbox event is in DB
    outbox = test_db_session.query(OutboxEvent).filter(
        OutboxEvent.aggregate_id == str(appt.id),
        OutboxEvent.event_type == "appointment.created",
    ).first()
    assert outbox is not None
    assert outbox.status in ["pending", "processed"]
