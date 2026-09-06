from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.application.field_service_workflow import (
    run_field_service_workflow,
)
from fieldops.application.persistence import (
    persist_customer_and_service_request,
)
from fieldops.db.models import Customer, ServiceRequest
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app
from fieldops.repositories.customer_repository import CustomerRepository
from fieldops.repositories.service_request_repository import (
    ServiceRequestRepository,
)
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)


def test_persist_new_customer_and_service_request(test_db_session: Session) -> None:
    """Test creating new customer and service request atomically."""
    c_id, sr_id = persist_customer_and_service_request(
        customer_name="Alice Smith",
        customer_email="alice@example.com",
        customer_phone="090-1111-2222",
        raw_message="AC is not working",
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        session=test_db_session,
    )

    assert isinstance(c_id, int)
    assert isinstance(sr_id, int)

    cust_repo = CustomerRepository(test_db_session)
    sr_repo = ServiceRequestRepository(test_db_session)

    customer = cust_repo.get_by_id(c_id)
    assert customer is not None
    assert customer.email == "alice@example.com"
    assert customer.name == "Alice Smith"

    service_request = sr_repo.get_by_id(sr_id)
    assert service_request is not None
    assert service_request.customer_id == c_id
    assert service_request.service_type == "HVAC"
    assert service_request.urgency == "high"
    assert service_request.status == "created"


def test_persist_existing_customer_reuse_no_duplicates(test_db_session: Session) -> None:
    """Test existing customer is reused by email without creating duplicates."""
    # First request
    c_id_1, sr_id_1 = persist_customer_and_service_request(
        customer_name="Bob Jones",
        customer_email="bob@example.com",
        customer_phone="090-3333-4444",
        raw_message="Kitchen sink leak",
        service_type="Plumbing",
        urgency="medium",
        location="Shinjuku",
        session=test_db_session,
    )

    # Second request with same email but different phone/name
    c_id_2, sr_id_2 = persist_customer_and_service_request(
        customer_name="Bob J.",
        customer_email="bob@example.com",
        customer_phone="090-9999-9999",
        raw_message="Water heater broken",
        service_type="Plumbing",
        urgency="high",
        location="Shinjuku",
        session=test_db_session,
    )

    # Must reuse the same customer ID
    assert c_id_1 == c_id_2
    assert sr_id_1 != sr_id_2

    # Total customers in DB must be exactly 1
    total_customers = test_db_session.scalars(select(Customer)).all()
    assert len(total_customers) == 1

    # Total service requests must be 2, both linked to the same customer
    total_requests = test_db_session.scalars(select(ServiceRequest)).all()
    assert len(total_requests) == 2
    assert total_requests[0].customer_id == c_id_1
    assert total_requests[1].customer_id == c_id_1


def test_transaction_rollback_leaves_no_orphaned_customer(test_db_session: Session) -> None:
    """Test that failure to create ServiceRequest rolls back Customer creation."""
    with patch.object(
        ServiceRequestRepository,
        "create",
        side_effect=RuntimeError("Simulated DB Disk Full"),
    ):
        with pytest.raises(RuntimeError, match="Simulated DB Disk Full"):
            persist_customer_and_service_request(
                customer_name="Charlie",
                customer_email="charlie@example.com",
                customer_phone=None,
                raw_message="Need electrical work",
                service_type="Electrical",
                urgency="medium",
                location="Yokohama",
                session=test_db_session,
            )

    # Verify rollback: customer Charlie must NOT exist in database
    cust_repo = CustomerRepository(test_db_session)
    assert cust_repo.get_by_email("charlie@example.com") is None
    all_customers = test_db_session.scalars(select(Customer)).all()
    assert len(all_customers) == 0


def test_workflow_full_persistence_success(test_db_session: Session) -> None:
    """Test full LangGraph workflow persists customer and service request."""
    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="this afternoon",
        problem_description="AC unit stopped working",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="My AC stopped working and smells like burning. I'm in Shinjuku.",
            customer_name="Alice",
            email="alice@example.com",
            phone="123456",
        )

    assert final_state["workflow_status"] in ("ready_for_scheduling", "no_technician_available")
    assert isinstance(final_state["customer_id"], int)
    assert isinstance(final_state["service_request_id"], int)
    assert final_state["service_type"] == "HVAC"
    assert final_state["urgency"] == "high"

    # Verify database state
    sr = test_db_session.get(ServiceRequest, final_state["service_request_id"])
    assert sr is not None
    assert sr.customer_id == final_state["customer_id"]
    assert sr.status == "created"


def test_workflow_invalid_request_does_not_write_to_db(test_db_session: Session) -> None:
    """Test that fatal validation error terminates workflow at END and does not write to DB."""
    mock_parsed = ParsedServiceRequest(
        service_type="InvalidServiceType",  # Will fail validation
        urgency="high",
        location="Shinjuku",
        required_skills=[],
        preferred_time=None,
        problem_description="Invalid",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="Need invalid service",
            customer_name="Dave",
            email="dave@example.com",
            phone=None,
        )

    assert final_state["workflow_status"] == "needs_information"
    assert final_state["customer_id"] is None
    assert final_state["service_request_id"] is None

    # Database must remain empty
    assert len(test_db_session.scalars(select(Customer)).all()) == 0
    assert len(test_db_session.scalars(select(ServiceRequest)).all()) == 0


def test_api_create_service_request_endpoint_success() -> None:
    """Test POST /service-requests API creates and returns persisted record IDs."""
    mock_parsed = ParsedServiceRequest(
        service_type="Plumbing",
        urgency="medium",
        location="Shinjuku",
        required_skills=["Plumbing"],
        preferred_time="tomorrow morning",
        problem_description="Leaking kitchen faucet",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        response = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "123456",
                "message": "My kitchen faucet is leaking. I am in Shinjuku.",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert "request_id" in data
    assert isinstance(data["customer_id"], int)
    assert isinstance(data["service_request_id"], int)
    assert data["service_type"] == "Plumbing"
    assert data["urgency"] == "medium"
    assert data["location"] == "Shinjuku"
    assert data["workflow_status"] in ("ready_for_scheduling", "no_technician_available")


def test_api_create_service_request_invalid_email() -> None:
    """Test POST /service-requests with invalid email format returns 422."""
    response = client.post(
        "/service-requests",
        json={
            "customer_name": "Alice",
            "email": "invalid-email-address",
            "phone": "123456",
            "message": "AC is broken",
        },
    )
    assert response.status_code == 422


def test_api_create_service_request_empty_message() -> None:
    """Test POST /service-requests with empty message returns 400."""
    response = client.post(
        "/service-requests",
        json={
            "customer_name": "Alice",
            "email": "alice@example.com",
            "phone": "123456",
            "message": "   ",
        },
    )
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]
