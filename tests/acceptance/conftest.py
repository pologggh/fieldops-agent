"""Shared fixtures for Phase 26 Acceptance Test Suite."""

import os
import uuid
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
    Customer,
    CustomerAccount,
    DispatchPolicy,
    InternalUser,
    SLAPolicy,
)
from fieldops.security.admin_auth import hash_password as hash_admin_pw


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
