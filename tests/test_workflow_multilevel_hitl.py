"""Tests for Phase 28 Multi-Level HITL and Resumption Role Verification."""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fieldops.agent.nodes.build_appointment_proposal import build_appointment_proposal_node
from fieldops.agent.state import create_initial_state
from fieldops.application.field_service_workflow import (
    resume_field_service_workflow,
    run_field_service_workflow,
)
from fieldops.core.exceptions import WorkflowStateError
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app)


def test_emergency_proposal_assigns_senior_operator(test_db_session: Session):
    """Emergency priority ticket proposal requires Senior Operator review."""
    seed_technicians(test_db_session)
    state = create_initial_state("req-hitl-1", "Emergency gas leak")
    state["service_request_id"] = 1
    state["urgency"] = "emergency"
    state["candidate_technician_ids"] = [1]
    state["available_options"] = [{
        "technician_id": 1,
        "start_time": "2026-09-07T10:00:00+09:00",
        "end_time": "2026-09-07T12:00:00+09:00",
    }]

    res = build_appointment_proposal_node(state)
    assert res["human_review_required"] is True
    assert res["human_review_level"] == "senior_operator"
    assert res["last_decision"]["reason_code"] == "EMERGENCY_REQUIRES_ELEVATED_APPROVAL"


def test_standard_proposal_assigns_operator(test_db_session: Session):
    """Low/Medium priority ticket proposal requires standard Operator review."""
    seed_technicians(test_db_session)
    state = create_initial_state("req-hitl-2", "Low urgency inspection")
    state["service_request_id"] = 1
    state["urgency"] = "low"
    state["candidate_technician_ids"] = [1]
    state["available_options"] = [{
        "technician_id": 1,
        "start_time": "2026-09-07T10:00:00+09:00",
        "end_time": "2026-09-07T12:00:00+09:00",
    }]

    res = build_appointment_proposal_node(state)
    assert res["human_review_required"] is True
    assert res["human_review_level"] == "operator"


def test_resume_insufficient_role_raises_error(test_db_session: Session):
    """Attempting to resume a Senior Operator proposal with Operator role fails."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="emergency",  # requires senior_operator
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow morning",
        problem_description="Dangerous failure",
    )

    with patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=mock_parsed):
        state = run_field_service_workflow(
            message="Dangerous failure in Shinjuku",
            request_id="req-hitl-senior",
        )

    assert state["workflow_status"] == "waiting_for_approval"
    assert state["human_review_level"] == "senior_operator"

    # Operator role resume attempt should fail
    with pytest.raises(WorkflowStateError) as exc:
        resume_field_service_workflow(
            request_id="req-hitl-senior",
            decision="approve",
            actor_role="operator",
        )
    assert "cannot approve proposal requiring 'senior_operator'" in str(exc.value)

    # Senior Operator or Admin resume attempt succeeds
    resumed = resume_field_service_workflow(
        request_id="req-hitl-senior",
        decision="approve",
        actor_role="senior_operator",
    )
    assert resumed["workflow_status"] == "appointment_created"
    assert resumed["approval_status"] == "approved"
