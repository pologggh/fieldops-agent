from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langgraph.graph import END

from fieldops.agent.graph import field_service_graph, route_after_validation
from fieldops.agent.nodes.parse_request import parse_request_node
from fieldops.agent.nodes.prepare_service_request import (
    prepare_service_request_node,
)
from fieldops.agent.nodes.validate_request import validate_request_node
from fieldops.agent.state import FieldServiceState, create_initial_state
from fieldops.application import run_field_service_workflow
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app

client = TestClient(app)


def test_create_initial_state() -> None:
    """1. Test that initial state is cleanly and properly initialized."""
    state = create_initial_state(
        request_id="test-req-123", raw_message="My heater is broken"
    )
    assert state["request_id"] == "test-req-123"
    assert state["raw_message"] == "My heater is broken"
    assert state["service_type"] is None
    assert state["urgency"] is None
    assert state["location"] is None
    assert state["required_skills"] == []
    assert state["preferred_time"] is None
    assert state["problem_description"] is None
    assert state["validation_errors"] == []
    assert state["workflow_status"] == "pending"


def test_parse_request_node_updates_state() -> None:
    """2. Test parse_request_node updates state using mock ParsedServiceRequest."""
    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="this afternoon",
        problem_description="AC unit stopped working",
    )

    initial_state = create_initial_state("req-1", "AC stopped working")
    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        result = parse_request_node(initial_state)

    assert result["service_type"] == "HVAC"
    assert result["urgency"] == "high"
    assert result["location"] == "Shinjuku"
    assert result["required_skills"] == ["HVAC"]
    assert result["preferred_time"] == "this afternoon"
    assert result["problem_description"] == "AC unit stopped working"
    assert result["workflow_status"] == "parsed"


def test_validate_request_node_valid_data() -> None:
    """3. Test validate_request_node passes valid inputs without errors."""
    state: FieldServiceState = {
        "request_id": "req-1",
        "raw_message": "AC broken in Shinjuku",
        "service_type": "HVAC",
        "urgency": "high",
        "location": "Shinjuku",
        "required_skills": ["HVAC"],
        "preferred_time": "this afternoon",
        "problem_description": "AC broken",
        "validation_errors": [],
        "workflow_status": "parsed",
    }

    result = validate_request_node(state)
    assert result["workflow_status"] == "validated"
    assert result["validation_errors"] == []


def test_validate_request_node_invalid_urgency() -> None:
    """4. Test validate_request_node detects invalid urgency."""
    state: FieldServiceState = {
        "request_id": "req-1",
        "raw_message": "Need help immediately",
        "service_type": "HVAC",
        "urgency": "super urgent",  # Invalid urgency
        "location": "Shinjuku",
        "required_skills": ["HVAC"],
        "preferred_time": None,
        "problem_description": "Broken AC",
        "validation_errors": [],
        "workflow_status": "parsed",
    }

    result = validate_request_node(state)
    assert result["workflow_status"] == "needs_information"
    assert any("Invalid urgency 'super urgent'" in err for err in result["validation_errors"])


def test_validate_request_node_missing_location_behavior() -> None:
    """5. Test missing location is recorded as non-fatal validation error/warning."""
    state: FieldServiceState = {
        "request_id": "req-1",
        "raw_message": "AC broken somewhere",
        "service_type": "HVAC",
        "urgency": "medium",
        "location": None,  # Missing location
        "required_skills": ["HVAC"],
        "preferred_time": None,
        "problem_description": "Broken AC",
        "validation_errors": [],
        "workflow_status": "parsed",
    }

    result = validate_request_node(state)
    # Location missing is non-fatal: workflow_status should still be validated
    assert result["workflow_status"] == "validated"
    assert any("missing_location" in err for err in result["validation_errors"])


def test_conditional_edge_routing() -> None:
    """6 & 7. Test conditional routing transitions to prepare vs END based on validation status."""
    # Valid state -> routes to prepare_service_request
    valid_state: FieldServiceState = {
        "request_id": "req-1",
        "raw_message": "test",
        "service_type": "HVAC",
        "urgency": "high",
        "location": "Shinjuku",
        "required_skills": ["HVAC"],
        "preferred_time": None,
        "problem_description": "test",
        "validation_errors": [],
        "workflow_status": "validated",
    }
    assert route_after_validation(valid_state) == "persist_service_request"

    # Invalid state -> routes directly to END
    invalid_state: FieldServiceState = {
        "request_id": "req-2",
        "raw_message": "test",
        "service_type": "UnknownType",
        "urgency": "high",
        "location": None,
        "required_skills": [],
        "preferred_time": None,
        "problem_description": "test",
        "validation_errors": ["Invalid service_type"],
        "workflow_status": "needs_information",
    }
    assert route_after_validation(invalid_state) == END


def test_prepare_service_request_node() -> None:
    """Test prepare_service_request_node promotes validated state."""
    state: FieldServiceState = {
        "request_id": "req-1",
        "raw_message": "test",
        "service_type": "HVAC",
        "urgency": "high",
        "location": "Shinjuku",
        "required_skills": ["HVAC"],
        "preferred_time": None,
        "problem_description": "test",
        "validation_errors": [],
        "workflow_status": "validated",
    }
    update = prepare_service_request_node(state)
    assert update["workflow_status"] == "ready_for_service_request"


def test_full_graph_execution_success() -> None:
    """8. Test full workflow graph completes with ready_for_service_request for valid input."""
    mock_parsed = ParsedServiceRequest(
        service_type="Plumbing",
        urgency="emergency",
        location="Yokohama",
        required_skills=["Plumbing"],
        preferred_time="tomorrow morning",
        problem_description="Pipe burst and flooding bathroom",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="Pipe burst and flooding bathroom in Yokohama!",
            request_id="custom-req-id-123",
        )

    assert final_state["request_id"] == "custom-req-id-123"
    assert final_state["service_type"] == "Plumbing"
    assert final_state["urgency"] == "emergency"
    assert final_state["location"] == "Yokohama"
    assert final_state["required_skills"] == ["Plumbing"]
    assert final_state["workflow_status"] in ("ready_for_scheduling", "no_technician_available")
    assert isinstance(final_state["customer_id"], int)
    assert isinstance(final_state["service_request_id"], int)
    assert final_state["validation_errors"] == []


def test_full_graph_execution_invalid_data_stops_at_end() -> None:
    """8b. Test invalid parsed data routes to END without running prepare_service_request."""
    mock_parsed = ParsedServiceRequest(
        service_type="Rocket Science",  # Disallowed service_type
        urgency="high",
        location="Yokohama",
        required_skills=["Space Travel"],
        preferred_time=None,
        problem_description="Need rocket repair",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="Need rocket repair",
            request_id="invalid-req-1",
        )

    assert final_state["workflow_status"] == "needs_information"
    assert any("Invalid service_type" in err for err in final_state["validation_errors"])


def test_api_service_requests_analyze_endpoint_success() -> None:
    """9. Test POST /service-requests/analyze FastAPI endpoint."""
    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="this afternoon",
        problem_description="AC unit stopped working with burning smell",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        response = client.post(
            "/service-requests/analyze",
            json={
                "message": "My AC stopped working and there is a burning smell. I'm in Shinjuku and need someone this afternoon."
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert data["service_type"] == "HVAC"
    assert data["urgency"] == "high"
    assert data["location"] == "Shinjuku"
    assert data["required_skills"] == ["HVAC"]
    assert data["preferred_time"] == "this afternoon"
    assert data["workflow_status"] in ("ready_for_scheduling", "no_technician_available")
    assert data["validation_errors"] == []


def test_api_service_requests_analyze_empty_message() -> None:
    """Test POST /service-requests/analyze with empty message returns HTTP 400."""
    response = client.post("/service-requests/analyze", json={"message": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]
