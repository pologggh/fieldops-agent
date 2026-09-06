import uuid
import pytest
from fastapi.testclient import TestClient

from fieldops.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unique_email():
    return f"customer_{uuid.uuid4().hex[:8]}@example.com"


def test_customer_registration_and_login(client, unique_email):
    reg_payload = {
        "name": "Jane Doe",
        "email": unique_email,
        "password": "SecretPassword123!",
        "phone": "555-0199",
    }
    resp = client.post("/customer-auth/register", json=reg_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["success"] is True
    assert data["customer"]["email"] == unique_email

    dup_resp = client.post("/customer-auth/register", json=reg_payload)
    assert dup_resp.status_code == 400

    login_resp = client.post(
        "/customer-auth/login",
        json={"email": unique_email, "password": "SecretPassword123!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data

    bad_login = client.post(
        "/customer-auth/login",
        json={"email": unique_email, "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401


def test_strict_token_boundary_enforcement(client, unique_email):
    resp = client.post(
        "/customer-auth/register",
        json={
            "name": "Boundary Test User",
            "email": unique_email,
            "password": "Password123!",
        },
    )
    assert resp.status_code == 201
    cust_token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {cust_token}"}

    me_resp = client.get("/customer/me", headers=headers)
    assert me_resp.status_code == 200

    auth_me_resp = client.get("/auth/me", headers=headers)
    assert auth_me_resp.status_code == 403

    sr_resp = client.get("/service-requests", headers=headers)
    assert sr_resp.status_code == 403


def test_anti_idor_data_isolation(client):
    email_a = f"cust_a_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"cust_b_{uuid.uuid4().hex[:8]}@example.com"

    resp_a = client.post(
        "/customer-auth/register",
        json={"name": "Alice Customer", "email": email_a, "password": "Password123!"},
    )
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp_b = client.post(
        "/customer-auth/register",
        json={"name": "Bob Customer", "email": email_b, "password": "Password123!"},
    )
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    sr_create = client.post(
        "/customer/requests",
        headers=headers_a,
        json={
            "service_type": "HVAC Repair",
            "problem_description": "Furnace not blowing warm air",
            "location": "North District Building 4",
            "preferred_time": "Tomorrow morning",
        },
    )
    assert sr_create.status_code == 201
    sr_a_id = sr_create.json()["id"]

    own_view = client.get(f"/customer/requests/{sr_a_id}", headers=headers_a)
    assert own_view.status_code == 200

    idor_get = client.get(f"/customer/requests/{sr_a_id}", headers=headers_b)
    assert idor_get.status_code == 404

    idor_supp = client.post(
        f"/customer/requests/{sr_a_id}/supplement",
        headers=headers_b,
        json={"additional_details": "Malicious", "location": "Hacked"},
    )
    assert idor_supp.status_code == 404

    idor_cancel = client.post(
        f"/customer/requests/{sr_a_id}/cancel",
        headers=headers_b,
        json={"reason": "Malicious cancel"},
    )
    assert idor_cancel.status_code == 404

    idor_resched = client.post(
        f"/customer/requests/{sr_a_id}/reschedule",
        headers=headers_b,
        json={"preferred_time": "Next week"},
    )
    assert idor_resched.status_code == 404

    list_b = client.get("/customer/requests", headers=headers_b)
    assert list_b.status_code == 200
    req_ids_b = [r["id"] for r in list_b.json()]
    assert sr_a_id not in req_ids_b


def test_customer_request_lifecycle_and_actions(client, unique_email):
    reg_resp = client.post(
        "/customer-auth/register",
        json={"name": "Lifecycle User", "email": unique_email, "password": "Password123!"},
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/customer/requests",
        headers=headers,
        json={
            "service_type": "Plumbing",
            "problem_description": "Water leak under sink",
        },
    )
    assert create_resp.status_code == 201
    sr = create_resp.json()
    sr_id = sr["id"]
    assert sr["needs_information"] is True
    assert "location" in sr["missing_fields"]
    assert sr["customer_status"] == "More information needed"

    supp_resp = client.post(
        f"/customer/requests/{sr_id}/supplement",
        headers=headers,
        json={
            "location": "742 Evergreen Terrace",
            "preferred_time": "Friday 2 PM",
            "additional_details": "Main pipe shutoff is behind cabinet",
        },
    )
    assert supp_resp.status_code == 200
    sr_updated = supp_resp.json()
    assert sr_updated["location"] == "742 Evergreen Terrace"
    assert sr_updated["needs_information"] is False

    cancel_resp = client.post(
        f"/customer/requests/{sr_id}/cancel",
        headers=headers,
        json={"reason": "Fixed it myself"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["customer_status"] == "Cancelled"
    assert cancel_resp.json()["can_cancel"] is False


def test_customer_profile_management(client, unique_email):
    reg_resp = client.post(
        "/customer-auth/register",
        json={
            "name": "Original Name",
            "email": unique_email,
            "password": "Password123!",
            "phone": "111-222-3333",
        },
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    get_prof = client.get("/customer/me", headers=headers)
    assert get_prof.status_code == 200
    assert get_prof.json()["name"] == "Original Name"

    patch_prof = client.patch(
        "/customer/me",
        headers=headers,
        json={"name": "Updated Name", "phone": "999-888-7777", "address": "123 Main St"},
    )
    assert patch_prof.status_code == 200
    updated = patch_prof.json()
    assert updated["name"] == "Updated Name"
    assert updated["phone"] == "999-888-7777"


def test_customer_summary_and_timeline(client, unique_email):
    reg_resp = client.post(
        "/customer-auth/register",
        json={"name": "Summary User", "email": unique_email, "password": "Password123!"},
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    sr_resp = client.post(
        "/customer/requests",
        headers=headers,
        json={
            "service_type": "Electrical",
            "problem_description": "Outlets sparking",
            "location": "Suite 100",
            "preferred_time": "Monday 9 AM",
        },
    )
    assert sr_resp.status_code == 201
    sr_data = sr_resp.json()

    timeline = sr_data["timeline"]
    assert len(timeline) >= 1
    for item in timeline:
        assert "sla_deadline" not in item
        assert "ranking" not in item
        assert "operator" not in item.get("title", "").lower()

    sum_resp = client.get("/customer/summary", headers=headers)
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["active_requests_count"] >= 1
