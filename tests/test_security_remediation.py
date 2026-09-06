"""Security Remediation & Regression Test Suite.

Verifies all 16 required security criteria:
1. Unauthenticated read of internal SR, appointments, technicians -> 401
2. Unauthenticated write (approval, start, complete, cancel, reassign) -> 401
3. Random, expired, tampered, and fixed mock tokens -> 401
4. Known old default secrets -> 401
5. Missing or malformed JWT claims -> 401 (never 500)
6. Cross-boundary token abuse (customer -> internal: 403; internal -> customer: 403)
7. Viewer can read (200) but cannot write (403)
8. Operator cannot access admin endpoints (403)
9. Deactivated or role-changed accounts immediately reflected from DB (403/401)
10. Password changed in DB invalidates old password and hardcoded defaults (401)
11. Missing admin in DB does not create a virtual admin (401)
12. /auth/me with invalid token returns 401 (not default operator)
13. Customer resource tenant isolation (Anti-IDOR) -> 404
14. Normal login, authorized read, approval, and appointment lifecycle -> 200
15. Custom JWT_SECRET validation: missing/insecure keys fail Settings validation
16. Public endpoints (/health, /metrics, etc.) work; Webhook invalid secret -> 401
"""

from datetime import datetime, timedelta, timezone
import os
import uuid
import bcrypt
from fastapi.testclient import TestClient
import jwt
import pytest
from pydantic import ValidationError

from fieldops.main import app
from fieldops.db.models import (
    Appointment,
    Customer,
    CustomerAccount,
    DispatchPolicy,
    InternalUser,
    ServiceRequest,
    SLAPolicy,
    Technician,
)
from fieldops.core.config import Settings


def _hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@pytest.fixture
def test_client(test_db_session):
    return TestClient(app)


@pytest.fixture
def seeded_users(test_db_session):
    """Seed test users in isolated DB session."""
    admin = InternalUser(
        email="test_admin@fieldops.com",
        name="Test Admin",
        role="admin",
        password_hash=_hash_pw("AdminPass123!"),
        is_active=True,
    )
    operator = InternalUser(
        email="test_operator@fieldops.com",
        name="Test Operator",
        role="operator",
        password_hash=_hash_pw("OperatorPass123!"),
        is_active=True,
    )
    viewer = InternalUser(
        email="test_viewer@fieldops.com",
        name="Test Viewer",
        role="viewer",
        password_hash=_hash_pw("ViewerPass123!"),
        is_active=True,
    )
    test_db_session.add_all([admin, operator, viewer])
    test_db_session.flush()

    # Seed sample technician
    tech = Technician(
        name="Test Technician",
        service_area="Tokyo",
        status="available",
        max_daily_work_minutes=480,
    )
    test_db_session.add(tech)
    test_db_session.flush()

    # Seed sample customer & request & appointment
    cust = Customer(name="Test Customer", email="cust@test.com", phone="12345678")
    test_db_session.add(cust)
    test_db_session.flush()

    sr = ServiceRequest(
        customer_id=cust.id,
        raw_message="Test HVAC breakdown",
        service_type="HVAC",
        urgency="medium",
        status="received",
        location="Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    appt = Appointment(
        service_request_id=sr.id,
        technician_id=tech.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=2),
        end_time=datetime.now(timezone.utc) + timedelta(hours=4),
        status="confirmed",
    )
    test_db_session.add(appt)
    test_db_session.commit()

    return {
        "admin": admin,
        "operator": operator,
        "viewer": viewer,
        "technician": tech,
        "customer": cust,
        "sr": sr,
        "appointment": appt,
    }


# ==============================================================================
# 1. Unauthenticated Read Rejected (401)
# ==============================================================================
@pytest.mark.parametrize("endpoint", [
    "/service-requests",
    "/appointments",
    "/technicians",
    "/escalations",
    "/system/status",
    "/dashboard/summary",
])
def test_01_unauthenticated_read_rejected(test_client, seeded_users, endpoint):
    res = test_client.get(endpoint)
    assert res.status_code == 401, f"Expected 401 on {endpoint}, got {res.status_code}: {res.text}"


# ==============================================================================
# 2. Unauthenticated Write Rejected (401)
# ==============================================================================
def test_02_unauthenticated_write_rejected(test_client, seeded_users):
    appt_id = seeded_users["appointment"].id
    sr_id = seeded_users["sr"].id

    endpoints = [
        ("post", f"/appointments/{appt_id}/start", {}),
        ("post", f"/appointments/{appt_id}/complete", {"completion_notes": "Done"}),
        ("post", f"/appointments/{appt_id}/cancel", {"reason": "Cancelled"}),
        ("post", f"/appointments/{appt_id}/reassign", {"technician_id": seeded_users["technician"].id}),
        ("post", f"/service-requests/{sr_id}/approval", {"decision": "approve"}),
        ("post", "/service-requests", {"message": "New request", "source": "call_center"}),
    ]

    for method, path, payload in endpoints:
        call = getattr(test_client, method)
        res = call(path, json=payload)
        assert res.status_code == 401, f"Expected 401 on {path}, got {res.status_code}: {res.text}"


# ==============================================================================
# 3. Random, Expired, Tampered, and Fixed Mock Tokens Rejected (401)
# ==============================================================================
@pytest.mark.parametrize("bad_token", [
    "mock-jwt-token",
    "jwt-token-admin-admin",
    "jwt-token-admin-admin@fieldops.com",
    "jwt-token-operator-operator",
    "jwt-token-viewer-viewer",
    "random-gibberish-string",
    "Bearer garbage.payload.signature",
])
def test_03_mock_and_garbage_tokens_rejected(test_client, seeded_users, bad_token):
    res = test_client.get("/service-requests", headers={"Authorization": f"Bearer {bad_token}"})
    assert res.status_code == 401, f"Token '{bad_token}' should be rejected with 401, got {res.status_code}"


def test_03_expired_and_tampered_token_rejected(test_client, seeded_users):
    from fieldops.core.config import settings

    # Expired token
    expired_payload = {
        "sub": str(seeded_users["admin"].id),
        "user_id": seeded_users["admin"].id,
        "email": seeded_users["admin"].email,
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    jwt_secret = getattr(settings, "JWT_SECRET", "test-secret-at-least-32-chars-long")
    expired_token = jwt.encode(expired_payload, jwt_secret, algorithm="HS256")

    res = test_client.get("/service-requests", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401, f"Expired token should return 401, got {res.status_code}"

    # Tampered signature token
    valid_payload = {
        "sub": str(seeded_users["admin"].id),
        "user_id": seeded_users["admin"].id,
        "email": seeded_users["admin"].email,
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    tampered_token = jwt.encode(valid_payload, "different-wrong-secret-key-at-least-32-chars", algorithm="HS256")
    res2 = test_client.get("/service-requests", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res2.status_code == 401, f"Tampered token should return 401, got {res2.status_code}"


# ==============================================================================
# 4. Old Known Default Secrets Rejected (401)
# ==============================================================================
@pytest.mark.parametrize("old_secret", [
    "fieldops-insecure-secret-key-change-in-production",
    "fieldops-admin-super-secret-key-change-in-production",
    "fieldops-customer-secret-key-change-in-production",
])
def test_04_old_default_secrets_rejected(test_client, seeded_users, old_secret):
    payload = {
        "sub": str(seeded_users["admin"].id),
        "user_id": seeded_users["admin"].id,
        "email": seeded_users["admin"].email,
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, old_secret, algorithm="HS256")
    res = test_client.get("/service-requests", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401, f"Token with old secret '{old_secret}' must return 401, got {res.status_code}"


# ==============================================================================
# 5. Missing or Malformed JWT Claims Returns Controlled 401 (Never 500)
# ==============================================================================
@pytest.mark.parametrize("bad_claims", [
    {},  # Empty
    {"role": "admin"},  # Missing sub & user_id
    {"sub": "not-an-integer", "user_id": "bad"},  # Malformed non-integer ID
    {"sub": None, "user_id": None},
    {"account_type": "customer", "sub": "invalid-int", "customer_id": "bad"},
])
def test_05_malformed_claims_returns_401_not_500(test_client, seeded_users, bad_claims):
    from fieldops.core.config import settings
    jwt_secret = getattr(settings, "JWT_SECRET", "test-secret-at-least-32-chars-long")

    claims = {**bad_claims, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(claims, jwt_secret, algorithm="HS256")

    # Test on internal endpoint
    res_int = test_client.get("/service-requests", headers={"Authorization": f"Bearer {token}"})
    assert res_int.status_code in (401, 403), f"Expected 401 or 403, got {res_int.status_code}: {res_int.text}"
    assert res_int.status_code != 500, "Must never return 500 on malformed claims"

    # Test on customer endpoint
    res_cust = test_client.get("/customer/requests", headers={"Authorization": f"Bearer {token}"})
    assert res_cust.status_code in (401, 403), f"Expected 401 or 403, got {res_cust.status_code}: {res_cust.text}"
    assert res_cust.status_code != 500, "Must never return 500 on malformed claims"


# ==============================================================================
# 6. Cross-Boundary Token Abuse Rejected (403)
# ==============================================================================
def test_06_cross_boundary_token_abuse(test_client, seeded_users):
    from fieldops.core.config import settings
    jwt_secret = getattr(settings, "JWT_SECRET", "test-secret-at-least-32-chars-long")

    # Valid Customer Token
    cust_token = jwt.encode({
        "sub": "1",
        "customer_id": 1,
        "type": "customer",
        "account_type": "customer",
        "email": "cust@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }, jwt_secret, algorithm="HS256")

    # Customer token accessing internal routes -> 403
    for path in ["/service-requests", "/appointments", "/technicians", "/admin/users"]:
        res = test_client.get(path, headers={"Authorization": f"Bearer {cust_token}"})
        assert res.status_code == 403, f"Customer token accessing {path} must return 403, got {res.status_code}"

    # Valid Internal Token
    internal_token = jwt.encode({
        "sub": str(seeded_users["operator"].id),
        "user_id": seeded_users["operator"].id,
        "type": "access",
        "role": "operator",
        "email": seeded_users["operator"].email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }, jwt_secret, algorithm="HS256")

    # Internal token accessing customer routes -> 403
    for path in ["/customer/requests", "/customer/appointments", "/customer/me"]:
        res = test_client.get(path, headers={"Authorization": f"Bearer {internal_token}"})
        assert res.status_code == 403, f"Internal token accessing {path} must return 403, got {res.status_code}"


# ==============================================================================
# 7. Viewer Role: Read Allowed (200), Write Rejected (403)
# ==============================================================================
def test_07_viewer_role_boundaries(test_client, seeded_users):
    # Log in as viewer
    login_res = test_client.post("/auth/login", json={
        "username": seeded_users["viewer"].email,
        "password": "ViewerPass123!",
    })
    assert login_res.status_code == 200
    viewer_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Reads: Allowed
    assert test_client.get("/service-requests", headers=viewer_headers).status_code == 200
    assert test_client.get("/appointments", headers=viewer_headers).status_code == 200
    assert test_client.get("/technicians", headers=viewer_headers).status_code == 200
    assert test_client.get("/dashboard/summary", headers=viewer_headers).status_code == 200

    # Writes: Rejected with 403
    appt_id = seeded_users["appointment"].id
    sr_id = seeded_users["sr"].id
    writes = [
        test_client.post(f"/appointments/{appt_id}/start", headers=viewer_headers),
        test_client.post(f"/appointments/{appt_id}/complete", headers=viewer_headers),
        test_client.post(f"/appointments/{appt_id}/cancel", headers=viewer_headers),
        test_client.post(f"/appointments/{appt_id}/reassign", headers=viewer_headers),
        test_client.post(f"/service-requests/{sr_id}/approval", headers=viewer_headers, json={"decision": "approve"}),
        test_client.post("/service-requests", headers=viewer_headers, json={"message": "fail"}),
    ]
    for w_res in writes:
        assert w_res.status_code == 403, f"Viewer write should be 403, got {w_res.status_code}: {w_res.text}"


# ==============================================================================
# 8. Operator Role Cannot Access Admin Endpoints (403)
# ==============================================================================
def test_08_operator_cannot_access_admin_endpoints(test_client, seeded_users):
    login_res = test_client.post("/auth/login", json={
        "username": seeded_users["operator"].email,
        "password": "OperatorPass123!",
    })
    assert login_res.status_code == 200
    op_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    admin_routes = [
        ("get", "/admin/users"),
        ("post", "/admin/users"),
        ("get", "/admin/technicians"),
        ("post", "/admin/technicians"),
        ("get", "/admin/policies/dispatch"),
        ("post", "/admin/policies/dispatch"),
        ("get", "/admin/policies/sla"),
        ("post", "/admin/policies/sla"),
        ("get", "/admin/audit"),
        ("get", "/admin/system/summary"),
    ]
    for method, path in admin_routes:
        call = getattr(test_client, method)
        res = call(path, headers=op_headers)
        assert res.status_code == 403, f"Operator accessing {path} must return 403, got {res.status_code}"


# ==============================================================================
# 9. Deactivated or Role-Changed Accounts Lose Permissions Immediately
# ==============================================================================
def test_09_deactivated_account_loses_permission(test_client, seeded_users, test_db_session):
    login_res = test_client.post("/auth/login", json={
        "username": seeded_users["operator"].email,
        "password": "OperatorPass123!",
    })
    assert login_res.status_code == 200
    op_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Verify access before deactivation
    assert test_client.get("/service-requests", headers=op_headers).status_code == 200

    # Deactivate account in DB
    user = test_db_session.query(InternalUser).filter_by(id=seeded_users["operator"].id).first()
    user.is_active = False
    test_db_session.commit()

    # Access immediately rejected (403 or 401)
    res_after = test_client.get("/service-requests", headers=op_headers)
    assert res_after.status_code in (401, 403), f"Deactivated user should be rejected, got {res_after.status_code}"

    # Also login should fail
    login_retry = test_client.post("/auth/login", json={
        "username": seeded_users["operator"].email,
        "password": "OperatorPass123!",
    })
    assert login_retry.status_code in (401, 403)


def test_09_role_demotion_reflected_immediately(test_client, seeded_users, test_db_session):
    login_res = test_client.post("/auth/login", json={
        "username": seeded_users["admin"].email,
        "password": "AdminPass123!",
    })
    assert login_res.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Demote admin to viewer in DB
    admin = test_db_session.query(InternalUser).filter_by(id=seeded_users["admin"].id).first()
    admin.role = "viewer"
    test_db_session.commit()

    # Now using the old token to access admin endpoint must return 403
    res_admin = test_client.get("/admin/users", headers=admin_headers)
    assert res_admin.status_code == 403, f"Demoted user must get 403 on admin endpoint, got {res_admin.status_code}"


# ==============================================================================
# 10. Changed Password Invalidates Old Password and Hardcoded Defaults
# ==============================================================================
def test_10_password_change_invalidates_old_and_default_passwords(test_client, seeded_users, test_db_session):
    # Change operator password in DB
    user = test_db_session.query(InternalUser).filter_by(id=seeded_users["operator"].id).first()
    user.password_hash = _hash_pw("BrandNewPassword999!")
    test_db_session.commit()

    # 1. Old password must fail
    res_old = test_client.post("/auth/login", json={
        "username": user.email,
        "password": "OperatorPass123!",
    })
    assert res_old.status_code == 401

    # 2. Hardcoded default password ("password123") must fail
    res_default = test_client.post("/auth/login", json={
        "username": user.email,
        "password": "password123",
    })
    assert res_default.status_code == 401

    # 3. New password succeeds
    res_new = test_client.post("/auth/login", json={
        "username": user.email,
        "password": "BrandNewPassword999!",
    })
    assert res_new.status_code == 200


# ==============================================================================
# 11. Missing Admin in DB Does Not Create Virtual Admin
# ==============================================================================
def test_11_missing_admin_does_not_synthesize_virtual_admin(test_client, test_db_session):
    # Delete all users from DB
    test_db_session.query(InternalUser).delete()
    test_db_session.commit()

    # Attempt to access admin console using mock token or signed token -> 401, not 200 with fake admin
    res = test_client.get("/admin/users", headers={"Authorization": "Bearer mock-jwt-token"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"

    # Query internal user table -> must remain completely empty (no virtual admin inserted or returned)
    admins_in_db = test_db_session.query(InternalUser).all()
    assert len(admins_in_db) == 0


# ==============================================================================
# 12. /auth/me Returns 401 on Invalid Credentials (Never Default Operator)
# ==============================================================================
@pytest.mark.parametrize("invalid_header", [
    None,
    "",
    "Bearer ",
    "Bearer invalid-random-token",
    "Bearer mock-jwt-token",
    "Bearer jwt-token-operator-operator",
])
def test_12_auth_me_rejects_invalid_tokens(test_client, seeded_users, invalid_header):
    headers = {"Authorization": invalid_header} if invalid_header is not None else {}
    res = test_client.get("/auth/me", headers=headers)
    assert res.status_code in (401, 403), f"Expected 401/403, got {res.status_code}: {res.text}"
    # Must never return default operator
    if res.status_code == 200:
        assert res.json().get("email") != "operator@fieldops.com"


# ==============================================================================
# 13. Customer Resource Tenant Isolation (Anti-IDOR) -> 404
# ==============================================================================
def test_13_customer_resource_tenant_isolation(test_client, test_db_session):
    # Register Customer Alpha
    res_a = test_client.post("/customer-auth/register", json={
        "name": "Cust Alpha",
        "email": "alpha@example.com",
        "password": "Password123!",
        "phone": "111",
    })
    assert res_a.status_code == 201
    headers_a = {"Authorization": f"Bearer {res_a.json()['access_token']}"}

    # Register Customer Beta
    res_b = test_client.post("/customer-auth/register", json={
        "name": "Cust Beta",
        "email": "beta@example.com",
        "password": "Password123!",
        "phone": "222",
    })
    assert res_b.status_code == 201
    headers_b = {"Authorization": f"Bearer {res_b.json()['access_token']}"}

    # Alpha creates a request
    req_res = test_client.post("/customer/requests", headers=headers_a, json={
        "problem_description": "Alpha private issue with HVAC unit.",
        "service_type": "HVAC",
        "location": "Tokyo",
    })
    assert req_res.status_code == 201
    alpha_req_id = req_res.json()["id"]

    # Beta attempts to read Alpha's request -> must return 404
    cross_read = test_client.get(f"/customer/requests/{alpha_req_id}", headers=headers_b)
    assert cross_read.status_code == 404, f"Cross-customer read should return 404, got {cross_read.status_code}"

    # Beta attempts to cancel Alpha's request -> must return 404
    cross_cancel = test_client.post(f"/customer/requests/{alpha_req_id}/cancel", headers=headers_b, json={"reason": "Malicious"})
    assert cross_cancel.status_code == 404, f"Cross-customer cancel should return 404, got {cross_cancel.status_code}"


# ==============================================================================
# 14. Normal Login, Authorized Read, Approval, and Lifecycle Functionality
# ==============================================================================
def test_14_happy_path_lifecycle(test_client, seeded_users):
    # 1. Login as operator
    login_res = test_client.post("/auth/login", json={
        "username": seeded_users["operator"].email,
        "password": "OperatorPass123!",
    })
    assert login_res.status_code == 200
    op_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 2. Check /auth/me returns operator details
    me_res = test_client.get("/auth/me", headers=op_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == seeded_users["operator"].email
    assert me_res.json()["role"] == "operator"

    # 3. Read appointments
    appts_res = test_client.get("/appointments", headers=op_headers)
    assert appts_res.status_code == 200

    # 4. Start appointment
    appt_id = seeded_users["appointment"].id
    start_res = test_client.post(f"/appointments/{appt_id}/start", headers=op_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "in_progress"

    # 5. Complete appointment
    comp_res = test_client.post(f"/appointments/{appt_id}/complete", headers=op_headers, json={
        "completion_notes": "Service successfully delivered.",
        "resolution_summary": "Replaced filter.",
    })
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"


# ==============================================================================
# 15. Settings Validation on Insecure or Missing JWT_SECRET
# ==============================================================================
def test_15_jwt_secret_settings_validation():
    # Test short secret (< 32 chars)
    with pytest.raises((ValidationError, ValueError)):
        Settings(JWT_SECRET="short-secret-key")

    # Test empty secret
    with pytest.raises((ValidationError, ValueError)):
        Settings(JWT_SECRET="")

    # Test known insecure default secret
    with pytest.raises((ValidationError, ValueError)):
        Settings(JWT_SECRET="fieldops-insecure-secret-key-change-in-production")

    with pytest.raises((ValidationError, ValueError)):
        Settings(JWT_SECRET="changeme")

    # Test valid high-entropy secret (>= 32 chars and not blacklisted)
    valid_settings = Settings(JWT_SECRET="a" * 32)
    assert valid_settings.JWT_SECRET == "a" * 32


# ==============================================================================
# 16. Public Endpoints & Webhook Security
# ==============================================================================
@pytest.mark.parametrize("public_path", [
    "/health",
    "/ready",
    "/metrics",
    "/openapi.json",
    "/docs",
])
def test_16_public_endpoints_accessible_without_auth(test_client, public_path):
    res = test_client.get(public_path)
    assert res.status_code == 200, f"Public endpoint {public_path} must return 200, got {res.status_code}"


def test_16_webhook_invalid_secret_rejected(test_client):
    # Webhook with missing or invalid secret -> 401
    res = test_client.post("/intake/webhook", json={
        "event_id": str(uuid.uuid4()),
        "event_type": "breakdown_reported",
        "customer": {"name": "External Cust", "phone": "12345", "address": "Tokyo"},
        "message": "Urgent breakdown",
    }, headers={"X-Webhook-Secret": "invalid-secret"})
    assert res.status_code == 401
