"""Unit tests for Phase 28 Workflow Subgraphs."""

from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from fieldops.agent.state import create_initial_state
from fieldops.agent.subgraphs import (
    build_dispatch_subgraph,
    build_escalation_subgraph,
    build_intake_subgraph,
    build_reschedule_subgraph,
)
from fieldops.llm.schemas import ParsedServiceRequest
from scripts.seed import seed_customers, seed_technicians


def test_intake_subgraph_valid(test_db_session: Session):
    """Test intake subgraph parses, validates, and persists valid customer request."""
    seed_customers(test_db_session)
    sg = build_intake_subgraph()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow morning",
        problem_description="AC broken and leaking",
    )

    state = create_initial_state("req-sg-intake-1", "AC broken in Shinjuku", customer_name="Alice", customer_email="alice@example.com")

    with patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=mock_parsed):
        result = sg.invoke(state)

    assert result["workflow_status"] == "service_request_created"
    assert result["customer_id"] is not None
    assert result["service_request_id"] is not None
    assert result["step_count"] >= 3
    assert result["last_decision"]["action"] == "dispatch"


def test_intake_subgraph_missing_field():
    """Test intake subgraph handles missing required fields and asks for information."""
    sg = build_intake_subgraph()

    mock_parsed = ParsedServiceRequest(
        service_type="UnknownType",  # Invalid/unsupported service type
        urgency="medium",
        location="Shinjuku",
        required_skills=[],
        preferred_time=None,
        problem_description="Need help",
    )

    state = create_initial_state("req-sg-intake-2", "Need help")

    with patch("fieldops.agent.nodes.parse_request.parse_service_request", return_value=mock_parsed):
        result = sg.invoke(state)

    assert result["workflow_status"] == "needs_information"
    assert result["clarification_count"] == 1
    assert result["last_decision"]["action"] == "ask_for_information"


def test_dispatch_subgraph_matched(test_db_session: Session):
    """Test dispatch subgraph successfully matches candidate and computes availability."""
    seed_technicians(test_db_session)
    sg = build_dispatch_subgraph()

    state = create_initial_state("req-sg-disp-1", "AC repair")
    state["service_type"] = "HVAC"
    state["urgency"] = "high"
    state["location"] = "Shinjuku"
    state["required_skills"] = ["HVAC"]
    state["preferred_time"] = "tomorrow afternoon"
    state["service_request_id"] = 1

    result = sg.invoke(state)
    assert result["workflow_status"] == "schedule_options_ready"
    assert len(result["candidate_technician_ids"]) >= 1
    assert len(result["available_options"]) >= 1
    assert result["last_decision"]["action"] == "wait_for_approval"


def test_dispatch_subgraph_no_candidates(test_db_session: Session):
    """Test dispatch subgraph triggers escalation when no technician has the required skill."""
    seed_technicians(test_db_session)
    sg = build_dispatch_subgraph()

    state = create_initial_state("req-sg-disp-2", "Solar panel install")
    state["service_type"] = "Other"
    state["urgency"] = "high"
    state["location"] = "Shinjuku"
    state["required_skills"] = ["Solar Engineering"]  # No tech has this skill
    state["preferred_time"] = "tomorrow afternoon"
    state["service_request_id"] = 1

    result = sg.invoke(state)
    assert result["workflow_status"] in ("no_technician_available", "escalated")
    assert result["last_decision"]["action"] == "escalate"
    assert result["last_decision"]["reason_code"] == "NO_ELIGIBLE_TECHNICIAN"


def test_reschedule_subgraph_bounded_loop():
    """Test reschedule subgraph increments count and escalates upon exceeding limit."""
    sg = build_reschedule_subgraph()

    # Round 1
    state = create_initial_state("req-sg-resched", "repair")
    state["reschedule_count"] = 0
    state["workflow_status"] = "needs_rescheduling"

    res1 = sg.invoke(state)
    assert res1["reschedule_count"] == 1
    assert res1["workflow_status"] == "ready_for_scheduling"

    # Round 3 (limit reached)
    state["reschedule_count"] = 3
    state["workflow_status"] = "needs_rescheduling"

    res_limit = sg.invoke(state)
    assert res_limit["workflow_status"] == "escalated"
    assert res_limit["escalation_details"]["reason_code"] == "RESCHEDULE_LIMIT_EXCEEDED"


def test_escalation_subgraph_execution(test_db_session: Session):
    """Test escalation subgraph writes audit log and sets status."""
    seed_customers(test_db_session)
    from fieldops.repositories.service_request_repository import ServiceRequestRepository
    sr = ServiceRequestRepository(test_db_session).create(1, "Fix AC", "HVAC", "high", "Shinjuku")
    test_db_session.commit()

    sg = build_escalation_subgraph()
    state = create_initial_state("req-sg-esc", "Fix AC")
    state["service_request_id"] = sr.id
    state["workflow_status"] = "pending"
    state["escalation_details"] = {
        "reason_code": "NO_ELIGIBLE_TECHNICIAN",
        "reason": "No technician available in zone.",
        "required_role": "operator",
        "severity": "P1",
    }

    result = sg.invoke(state)
    assert result["workflow_status"] in ("no_technician_available", "escalated")

    # Verify audit log was recorded
    from fieldops.db.models import AuditLog
    audit = test_db_session.query(AuditLog).filter_by(entity_id=str(sr.id), action="workflow.escalated").first()
    assert audit is not None
    assert audit.details["reason_code"] == "NO_ELIGIBLE_TECHNICIAN"
