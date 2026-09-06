import os
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from fieldops.agent.checkpointer import get_checkpointer
from fieldops.agent.graph import build_field_service_graph
from fieldops.agent.nodes.build_appointment_proposal import (
    build_appointment_proposal_node,
)
from fieldops.agent.state import create_initial_state
from fieldops.application.field_service_workflow import (
    WorkflowAlreadyCompletedError,
    WorkflowNotFoundError,
    resume_field_service_workflow,
    run_field_service_workflow,
)
from fieldops.domain.services.appointment_proposal import (
    AppointmentProposalService,
)
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)


# ==============================================================================
# 1. Unit & Service Tests: Appointment Proposal Deterministic Policy
# ==============================================================================


def test_appointment_proposal_service_empty() -> None:
    """Proposal service returns None when available_options is empty."""
    assert AppointmentProposalService.select_proposal([]) is None


def test_appointment_proposal_service_deterministic_ordering() -> None:
    """Proposal service deterministically selects earliest start_time, then lowest technician_id."""
    options = [
        {
            "technician_id": 3,
            "start_time": "2026-09-05T14:00:00+09:00",
            "end_time": "2026-09-05T16:00:00+09:00",
        },
        {
            "technician_id": 4,
            "start_time": "2026-09-05T13:00:00+09:00",
            "end_time": "2026-09-05T15:00:00+09:00",
        },
        {
            "technician_id": 1,
            "start_time": "2026-09-05T13:00:00+09:00",
            "end_time": "2026-09-05T15:00:00+09:00",
        },
    ]
    tech_names = {1: "Ken Tanaka", 3: "Satoshi Ono", 4: "Yuki Sato"}

    proposal = AppointmentProposalService.select_proposal(
        available_options=options,
        service_request_id=99,
        technician_names=tech_names,
    )

    assert proposal is not None
    # Earliest time is 13:00. Between tech 1 and tech 4, tech 1 wins tie-breaker.
    assert proposal["technician_id"] == 1
    assert proposal["technician_name"] == "Ken Tanaka"
    assert proposal["start_time"] == "2026-09-05T13:00:00+09:00"
    assert proposal["end_time"] == "2026-09-05T15:00:00+09:00"
    assert proposal["service_request_id"] == 99


def test_build_appointment_proposal_node(test_db_session: Session) -> None:
    """Test build_appointment_proposal_node populates proposal and updates status."""
    seed_technicians(test_db_session)

    state = create_initial_state("req-prop-1", "AC repair")
    state["service_request_id"] = 42
    state["candidate_technician_ids"] = [1, 2]
    state["available_options"] = [
        {
            "technician_id": 1,
            "start_time": "2026-09-05T13:00:00+09:00",
            "end_time": "2026-09-05T15:00:00+09:00",
        }
    ]

    result = build_appointment_proposal_node(state)
    assert result["workflow_status"] == "waiting_for_approval"
    assert result["approval_status"] == "pending"
    assert result["human_review_required"] is True
    assert result["appointment_proposal"] is not None
    assert result["appointment_proposal"]["technician_id"] == 1
    assert result["appointment_proposal"]["service_request_id"] == 42


# ==============================================================================
# 2. Workflow Pause and Resume Tests (HITL)
# ==============================================================================


def test_workflow_interrupts_at_human_review(test_db_session: Session) -> None:
    """Workflow pauses at human_review node when schedule options exist."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC stopped working with burning smell",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        state = run_field_service_workflow(
            message="My AC stopped working in Shinjuku tomorrow afternoon",
            customer_name="Alice",
            email="alice@example.com",
            request_id="workflow-pause-1",
        )

    assert state["workflow_status"] == "waiting_for_approval"
    assert state["approval_status"] == "pending"
    assert state["human_review_required"] is True
    assert state["appointment_proposal"] is not None
    assert state["appointment_proposal"]["technician_id"] in (1, 4)


def test_workflow_resume_approve(test_db_session: Session) -> None:
    """Workflow resumes with approve decision and transitions to approval_completed."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC stopped working",
    )

    req_id = "workflow-approve-1"
    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        run_field_service_workflow(
            message="AC repair Shinjuku tomorrow afternoon",
            customer_name="Alice",
            email="alice@example.com",
            request_id=req_id,
        )

    resumed_state = resume_field_service_workflow(
        request_id=req_id,
        decision="approve",
    )

    assert resumed_state["approval_status"] == "approved"
    assert resumed_state["workflow_status"] in ("approval_completed", "appointment_created")
    assert resumed_state["approval_reason"] is None
    assert resumed_state["appointment_id"] is not None


def test_workflow_resume_reject(test_db_session: Session) -> None:
    """Workflow resumes with reject decision, preserves reason, and transitions to rejected."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC stopped working",
    )

    req_id = "workflow-reject-1"
    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        run_field_service_workflow(
            message="AC repair Shinjuku tomorrow afternoon",
            customer_name="Alice",
            email="alice@example.com",
            request_id=req_id,
        )

    resumed_state = resume_field_service_workflow(
        request_id=req_id,
        decision="reject",
        reason="Customer requested next week instead",
    )

    assert resumed_state["approval_status"] == "rejected"
    assert resumed_state["workflow_status"] == "rejected"
    assert resumed_state["approval_reason"] == "Customer requested next week instead"


# ==============================================================================
# 3. FastAPI Approval Endpoint Tests & Error Handling (404, 409, 422)
# ==============================================================================


def test_api_approval_flow_approve(test_db_session: Session) -> None:
    """POST /service-requests initiates workflow, and POST /service-requests/{id}/approval approves it."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC repair",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        create_resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "123456",
                "message": "AC stopped working in Shinjuku tomorrow afternoon",
            },
        )

    assert create_resp.status_code == 201
    created_data = create_resp.json()
    req_id = created_data["request_id"]
    assert created_data["workflow_status"] == "waiting_for_approval"
    assert created_data["appointment_proposal"] is not None

    approval_resp = client.post(
        f"/service-requests/{req_id}/approval",
        json={"decision": "approve", "reason": None},
    )

    assert approval_resp.status_code == 200
    approval_data = approval_resp.json()
    assert approval_data["request_id"] == req_id
    assert approval_data["approval_status"] == "approved"
    assert approval_data["workflow_status"] in ("approval_completed", "appointment_created")
    assert approval_data["appointment_id"] is not None


def test_api_approval_flow_reject(test_db_session: Session) -> None:
    """POST /service-requests/{id}/approval rejects proposal and records rejection reason."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC repair",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        create_resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "123456",
                "message": "AC stopped working in Shinjuku tomorrow afternoon",
            },
        )

    assert create_resp.status_code == 201
    req_id = create_resp.json()["request_id"]

    approval_resp = client.post(
        f"/service-requests/{req_id}/approval",
        json={"decision": "reject", "reason": "Operator assigned different priority"},
    )

    assert approval_resp.status_code == 200
    approval_data = approval_resp.json()
    assert approval_data["approval_status"] == "rejected"
    assert approval_data["workflow_status"] == "rejected"
    assert approval_data["approval_reason"] == "Operator assigned different priority"


def test_api_approval_invalid_decision() -> None:
    """Approval endpoint validates decision field and rejects non-allowed strings with HTTP 422."""
    resp = client.post(
        "/service-requests/any-request-id/approval",
        json={"decision": "maybe", "reason": "undecided"},
    )
    assert resp.status_code == 422


def test_api_approval_unknown_request_id() -> None:
    """Approval endpoint returns HTTP 404 for non-existent request_id."""
    resp = client.post(
        "/service-requests/non-existent-request-id-12345/approval",
        json={"decision": "approve"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_approval_duplicate_conflict(test_db_session: Session) -> None:
    """Approval endpoint returns HTTP 409 Conflict when attempting to approve an already completed workflow."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC repair",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        create_resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "message": "AC repair Shinjuku tomorrow afternoon",
            },
        )

    req_id = create_resp.json()["request_id"]

    # First approval succeeds
    resp1 = client.post(
        f"/service-requests/{req_id}/approval",
        json={"decision": "approve"},
    )
    assert resp1.status_code == 200

    # Second approval returns 409 Conflict
    resp2 = client.post(
        f"/service-requests/{req_id}/approval",
        json={"decision": "approve"},
    )
    assert resp2.status_code == 409
    assert "not awaiting approval" in resp2.json()["detail"]


# ==============================================================================
# 4. Checkpoint Persistence Test Across Graph Instances (Section 22)
# ==============================================================================


def test_checkpoint_persistence_across_instances(test_db_session: Session) -> None:
    """Demonstrate that Human Approval persists across graph re-instantiations.

    Section 22 test:
    1. Start workflow on graph instance 1
    2. Interrupt at human_review
    3. Destroy graph instance 1
    4. Create graph instance 2 with the same SQLite checkpoint file
    5. Resume workflow using graph instance 2 on the same thread_id
    6. Confirm workflow continues and completes successfully.
    """
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        sqlite_file = os.path.join(tmpdir, "test_checkpoints.sqlite")
        checkpointer1 = get_checkpointer(db_path=sqlite_file)
        graph1 = build_field_service_graph(checkpointer=checkpointer1)

        mock_parsed = ParsedServiceRequest(
            service_type="HVAC",
            urgency="high",
            location="Shinjuku",
            required_skills=["HVAC"],
            preferred_time="tomorrow afternoon",
            problem_description="AC repair",
        )

        test_thread_id = "persisted-thread-001"

        # 1 & 2. Run workflow on graph1, which pauses at human_review
        with patch(
            "fieldops.agent.nodes.parse_request.parse_service_request",
            return_value=mock_parsed,
        ):
            paused_state = run_field_service_workflow(
                message="AC broken in Shinjuku tomorrow afternoon",
                customer_name="Alice",
                email="alice@example.com",
                request_id=test_thread_id,
                graph=graph1,
            )

        assert paused_state["workflow_status"] == "waiting_for_approval"
        assert paused_state["appointment_proposal"] is not None

        # 3. Destroy graph instance 1 and close its connection
        if hasattr(checkpointer1, "conn"):
            checkpointer1.conn.close()
        del graph1
        del checkpointer1

        # 4. Re-instantiate a completely fresh checkpointer and graph instance pointing to the same file
        checkpointer2 = get_checkpointer(db_path=sqlite_file)
        graph2 = build_field_service_graph(checkpointer=checkpointer2)

        # 5. Resume from graph instance 2
        resumed_state = resume_field_service_workflow(
            request_id=test_thread_id,
            decision="approve",
            graph=graph2,
        )

        # 6. Verify successful resumption and completion
        assert resumed_state["approval_status"] == "approved"
        assert resumed_state["workflow_status"] in ("approval_completed", "appointment_created")
        assert resumed_state["request_id"] == test_thread_id
        assert resumed_state["appointment_id"] is not None

        if hasattr(checkpointer2, "conn"):
            checkpointer2.conn.close()
