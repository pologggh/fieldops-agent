"""Tests for GET /internal/workflows/{request_id} debug inspection API."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fieldops.application.field_service_workflow import run_field_service_workflow
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app)


def test_internal_workflow_inspect_endpoint(test_db_session: Session):
    """Internal operator can inspect workflow state without leaking prompts."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="medium",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow morning",
        problem_description="AC not cooling",
    )

    with patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=mock_parsed):
        state = run_field_service_workflow(
            message="AC not cooling in Shinjuku",
            request_id="req-inspect-1",
        )

    # 1. Unauthenticated request rejected
    unauth = client.get("/internal/workflows/req-inspect-1")
    assert unauth.status_code == 401

    # 2. Authenticated operator request succeeds
    resp = client.get("/internal/workflows/req-inspect-1", headers=TEST_OPERATOR_HEADERS)
    assert resp.status_code == 200
    data = resp.json()

    assert data["request_id"] == "req-inspect-1"
    assert data["workflow_status"] == "waiting_for_approval"
    assert data["human_review_level"] == "operator"
    assert data["step_count"] >= 1
    assert data["last_decision"] is not None
    assert "prompt" not in data  # No prompt leakage
    assert "raw_message" not in data  # Minimal internal view
