"""Backend test suite for Phase 21C Admin Console.

- RBAC: Admin (200), Operator (403), Viewer (403), Customer (403), Unauthenticated (401)
- User Management & Soft-Disable
- Last Active Admin Protection
- Technician Conflict Check (409 Conflict)
- Dispatch & SLA Configuration Versioning & Rollback
- Zero Secret Exposure
"""

import os
import json
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///fieldops_demo.db"
os.environ["LOAD_TEST_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["APP_ENV"] = "testing"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fieldops.core.config import settings
settings.RATE_LIMIT_ENABLED = False
settings.LLM_PROVIDER = "fake"

from fieldops.main import app
from fieldops.db.session import Base
from fieldops.db.models import (
    Appointment, Customer, DispatchPolicy, InternalUser, ServiceRequest, SLAPolicy, Technician,
)
from fieldops.security.admin_auth import hash_password


from fieldops.db.session import SessionLocal, Base


@pytest.fixture
def client(test_db_session):
    admin = test_db_session.query(InternalUser).filter_by(email="admin@fieldops.com").first()
    if not admin:
        admin = InternalUser(
            email="admin@fieldops.com",
            name="Admin User",
            role="admin",
            password_hash=hash_password("password123"),
            is_active=True,
        )
        test_db_session.add(admin)
    else:
        admin.is_active = True
        admin.role = "admin"

    operator = test_db_session.query(InternalUser).filter_by(email="operator@fieldops.com").first()
    if not operator:
        operator = InternalUser(
            email="operator@fieldops.com",
            name="Senior Dispatcher",
            role="operator",
            password_hash=hash_password("password123"),
            is_active=True,
        )
        test_db_session.add(operator)
    else:
        operator.is_active = True

    viewer = test_db_session.query(InternalUser).filter_by(email="viewer@fieldops.com").first()
    if not viewer:
        viewer = InternalUser(
            email="viewer@fieldops.com",
            name="Auditor / Viewer",
            role="viewer",
            password_hash=hash_password("password123"),
            is_active=True,
        )
        test_db_session.add(viewer)
    else:
        viewer.is_active = True

    dp = test_db_session.query(DispatchPolicy).filter_by(version=1).first()
    if not dp:
        test_db_session.add(DispatchPolicy(
            version=1,
            is_active=True,
            weights={"workload_weight": 25, "capacity_weight": 20, "sla_weight": 30, "travel_weight": 15, "overtime_penalty": 10},
            description="Initial Dispatch Policy",
            created_by="test_setup",
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
            description="Initial SLA Policy",
            created_by="test_setup",
        ))
    test_db_session.commit()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_token(client):
    res = client.post("/auth/login", json={"username": "admin@fieldops.com", "password": "password123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
def operator_token(client):
    res = client.post("/auth/login", json={"username": "operator@fieldops.com", "password": "password123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
def viewer_token(client):
    res = client.post("/auth/login", json={"username": "viewer@fieldops.com", "password": "password123"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
def customer_token():
    import jwt
    from fieldops.security.customer_auth import JWT_SECRET, JWT_ALGORITHM
    return jwt.encode(
        {"sub": "999", "account_type": "customer", "type": "customer", "email": "hacker_customer@test.com"},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def test_rbac_admin_access_allowed(client, admin_token):
    res = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_rbac_operator_access_forbidden(client, operator_token):
    res = client.get("/admin/users", headers={"Authorization": f"Bearer {operator_token}"})
    assert res.status_code == 403
    assert "Admin privileges required" in res.json()["detail"]


def test_rbac_viewer_access_forbidden(client, viewer_token):
    res = client.get("/admin/users", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res.status_code == 403
    assert "Admin privileges required" in res.json()["detail"]


def test_rbac_customer_access_forbidden(client, customer_token):
    res = client.get("/admin/users", headers={"Authorization": f"Bearer {customer_token}"})
    assert res.status_code == 403


def test_rbac_unauthenticated_rejected(client):
    res = client.get("/admin/users")
    assert res.status_code == 401


def test_create_and_deactivate_internal_user(client, admin_token):
    disp_email = f"dispatcher_{uuid.uuid4().hex[:6]}@fieldops.com"
    res = client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": disp_email,
            "name": "Dispatcher Two",
            "role": "operator",
            "password": "securepassword123",
        },
    )
    assert res.status_code == 201
    user_data = res.json()
    user_id = user_data["id"]
    assert user_data["email"] == disp_email
    assert user_data["role"] == "operator"
    assert user_data["is_active"] is True

    login_res = client.post("/auth/login", json={"username": disp_email, "password": "securepassword123"})
    assert login_res.status_code == 200

    deact_res = client.post(f"/admin/users/{user_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    login_after = client.post("/auth/login", json={"username": disp_email, "password": "securepassword123"})
    assert login_after.status_code == 403
    assert "deactivated" in login_after.json()["detail"].lower()

    act_res = client.post(f"/admin/users/{user_id}/activate", headers={"Authorization": f"Bearer {admin_token}"})
    assert act_res.status_code == 200
    assert act_res.json()["is_active"] is True


def test_last_active_admin_protection(client, admin_token, test_db_session):
    # Delete any other admins created in previous tests so admin@fieldops.com is the only one
    test_db_session.query(InternalUser).filter(
        InternalUser.role == "admin",
        InternalUser.email != "admin@fieldops.com",
    ).delete()
    admin_u = test_db_session.query(InternalUser).filter_by(email="admin@fieldops.com").first()
    if admin_u:
        admin_u.is_active = True
    test_db_session.commit()

    users_res = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    admin_user = next(u for u in users_res.json() if u["email"] == "admin@fieldops.com")
    admin_id = admin_user["id"]

    deact_res = client.post(f"/admin/users/{admin_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    assert deact_res.status_code == 400
    assert "last active administrator" in deact_res.json()["detail"].lower()

    role_res = client.post(
        f"/admin/users/{admin_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "operator"},
    )
    assert role_res.status_code == 400
    assert "last active administrator" in role_res.json()["detail"].lower()

    backup_email = f"backupadmin_{uuid.uuid4().hex[:6]}@fieldops.com"
    client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": backup_email, "name": "Backup Admin", "role": "admin", "password": "password123"},
    )

    deact_ok = client.post(f"/admin/users/{admin_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    assert deact_ok.status_code == 200
    assert deact_ok.json()["is_active"] is False

    login_b = client.post("/auth/login", json={"username": backup_email, "password": "password123"})
    assert login_b.status_code == 200, login_b.text
    b_token = login_b.json()["access_token"]
    act_ok = client.post(f"/admin/users/{admin_id}/activate", headers={"Authorization": f"Bearer {b_token}"})
    assert act_ok.status_code == 200
    assert act_ok.json()["is_active"] is True


def test_technician_management_and_conflict_check(client, admin_token, test_db_session):
    res = client.post(
        "/admin/technicians",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Sarah Connor",
            "service_area": "North",
            "skills": ["HVAC", "Plumbing"],
            "max_daily_work_minutes": 480,
            "max_daily_jobs": 4,
            "is_available_for_emergency": True,
        },
    )
    assert res.status_code == 201
    tech = res.json()
    tech_id = tech["id"]
    assert tech["name"] == "Sarah Connor"
    assert tech["max_daily_work_minutes"] == 480
    assert tech["max_daily_jobs"] == 4
    assert tech["is_available_for_emergency"] is True

    patch_res = client.patch(
        f"/admin/technicians/{tech_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"max_daily_jobs": 5, "is_available_for_emergency": False},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["max_daily_jobs"] == 5
    assert patch_res.json()["is_available_for_emergency"] is False

    cust = test_db_session.query(Customer).first()
    if not cust:
        cust = Customer(name="Conflict Cust", email=f"conf_{int(datetime.now().timestamp())}@test.com")
        test_db_session.add(cust)
        test_db_session.flush()
    sr = ServiceRequest(
        customer_id=cust.id,
        raw_message="Future repair request",
        service_type="HVAC",
        urgency="high",
        location="North",
        status="scheduled",
    )
    test_db_session.add(sr)
    test_db_session.flush()
    future_start = datetime.now(timezone.utc) + timedelta(days=2)
    future_end = future_start + timedelta(hours=2)
    appt = Appointment(
        service_request_id=sr.id,
        technician_id=tech_id,
        start_time=future_start,
        end_time=future_end,
        status="scheduled",
    )
    test_db_session.add(appt)
    test_db_session.commit()

    deact_res = client.post(f"/admin/technicians/{tech_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    assert deact_res.status_code == 409
    assert "active future appointment" in deact_res.json()["detail"].lower()

    a = test_db_session.query(Appointment).filter_by(technician_id=tech_id).first()
    a.status = "cancelled"
    test_db_session.commit()

    deact_ok = client.post(f"/admin/technicians/{tech_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    assert deact_ok.status_code == 200
    assert deact_ok.json()["status"] == "inactive"


def test_dispatch_policy_versioning_and_rollback(client, admin_token):
    list_res = client.get("/admin/policies/dispatch", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    v1 = list_res.json()[0]
    assert v1["version"] == 1
    assert v1["is_active"] is True

    bad_res = client.post(
        "/admin/policies/dispatch",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "weights": {"workload_weight": 50, "capacity_weight": 20, "sla_weight": 20, "travel_weight": 5, "overtime_penalty": 0},
            "description": "Invalid weights sum 95",
        },
    )
    assert bad_res.status_code in [400, 422]

    create_res = client.post(
        "/admin/policies/dispatch",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "weights": {"workload_weight": 20, "capacity_weight": 20, "sla_weight": 40, "travel_weight": 10, "overtime_penalty": 10},
            "description": "SLA-focused weight policy",
            "set_active": True,
        },
    )
    assert create_res.status_code == 201
    v2 = create_res.json()
    assert v2["version"] == 2
    assert v2["is_active"] is True

    list_res2 = client.get("/admin/policies/dispatch", headers={"Authorization": f"Bearer {admin_token}"})
    v1_updated = next(p for p in list_res2.json() if p["version"] == 1)
    assert v1_updated["is_active"] is False

    rollback_res = client.post("/admin/policies/dispatch/1/activate", headers={"Authorization": f"Bearer {admin_token}"})
    assert rollback_res.status_code == 200
    assert rollback_res.json()["version"] == 1
    assert rollback_res.json()["is_active"] is True

    list_res3 = client.get("/admin/policies/dispatch", headers={"Authorization": f"Bearer {admin_token}"})
    v2_updated = next(p for p in list_res3.json() if p["version"] == 2)
    assert v2_updated["is_active"] is False


def test_sla_policy_and_historical_immutability(client, admin_token, test_db_session):
    cust = test_db_session.query(Customer).first()
    if not cust:
        cust = Customer(name="SLA Cust", email=f"sla_{int(datetime.now().timestamp())}@test.com")
        test_db_session.add(cust)
        test_db_session.flush()
    historical_sr = ServiceRequest(
        customer_id=cust.id,
        raw_message="Historical ticket",
        service_type="HVAC",
        urgency="P0",
        location="North",
        status="pending",
    )
    test_db_session.add(historical_sr)
    test_db_session.commit()
    sr_id = historical_sr.id
    original_created_at = historical_sr.created_at

    res = client.post(
        "/admin/policies/sla",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "targets": {
                "P0": {"response_minutes": 5, "assignment_minutes": 10, "service_start_minutes": 60, "at_risk_threshold_minutes": 5},
                "P1": {"response_minutes": 15, "assignment_minutes": 30, "service_start_minutes": 120, "at_risk_threshold_minutes": 15},
                "P2": {"response_minutes": 30, "assignment_minutes": 60, "service_start_minutes": 240, "at_risk_threshold_minutes": 30},
                "P3": {"response_minutes": 60, "assignment_minutes": 120, "service_start_minutes": 480, "at_risk_threshold_minutes": 60},
            },
            "description": "High-frequency emergency SLA targets",
            "set_active": True,
        },
    )
    assert res.status_code == 201
    assert res.json()["version"] >= 2

    check_sr = test_db_session.query(ServiceRequest).filter_by(id=sr_id).first()
    assert check_sr.status == "pending"
    assert check_sr.created_at == original_created_at


def test_integration_status_and_zero_secrets(client, admin_token):
    res = client.get("/admin/integrations/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    providers = data["providers"]
    for p in providers:
        assert p["is_mock"] is True
        assert "Development / Fake Provider" in p["badge"]

    text_content = res.text.lower()
    assert "password" not in text_content
    assert "secret" not in text_content
    assert "private_key" not in text_content


def test_audit_log_querying(client, admin_token):
    client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"audit_user_{uuid.uuid4().hex[:6]}@fieldops.com",
            "name": "Audit Test",
            "role": "viewer",
            "password": "password123",
        },
    )
    res = client.get("/admin/audit", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) > 0

    filtered = client.get("/admin/audit?entity_type=internal_user", headers={"Authorization": f"Bearer {admin_token}"})
    assert filtered.status_code == 200
    for l in filtered.json():
        assert l["entity_type"] == "internal_user"


def test_system_health_and_secret_concealment(client, admin_token):
    res = client.get("/admin/system/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "health_status" in data
    assert "readiness_status" in data
    assert "llm_config" in data
    assert data["llm_config"]["provider"] == "fake"
    assert data["llm_config"]["configured"] is True

    assert "api_key" not in data["llm_config"]
    assert "password" not in res.text.lower()
    assert "jwt_secret" not in res.text.lower()
