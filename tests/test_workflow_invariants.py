"""Unit tests for Phase 28 Workflow Invariants and State Transition Guard."""

import pytest

from fieldops.agent.invariants import (
    MAX_WORKFLOW_STEPS,
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.core.exceptions import WorkflowInvariantError


def test_valid_forward_transitions():
    """Verify standard happy-path state transitions are permitted."""
    valid_pairs = [
        ("pending", "parsed"),
        ("parsed", "validated"),
        ("validated", "service_request_created"),
        ("service_request_created", "ready_for_scheduling"),
        ("ready_for_scheduling", "schedule_options_ready"),
        ("schedule_options_ready", "waiting_for_approval"),
        ("waiting_for_approval", "approval_completed"),
        ("approval_completed", "appointment_created"),
        ("appointment_created", "in_progress"),
        ("in_progress", "completed"),
    ]
    for current, target in valid_pairs:
        # Must not raise
        validate_workflow_transition(current, target)


def test_illegal_backward_and_arbitrary_transitions():
    """Verify illegal transitions are strictly rejected by the transition guard."""
    illegal_pairs = [
        ("completed", "ready_for_scheduling"),
        ("completed", "parsed"),
        ("cancelled", "waiting_for_approval"),
        ("appointment_created", "parsed"),
        ("rejected", "ready_for_scheduling"),
        ("failed", "parsed"),
    ]
    for current, target in illegal_pairs:
        with pytest.raises(WorkflowInvariantError) as exc:
            validate_workflow_transition(current, target)
        assert "Illegal workflow state transition" in str(exc.value)


def test_self_transition_allowed():
    """Idempotent / re-entrant execution on the same state is permissible."""
    validate_workflow_transition("ready_for_scheduling", "ready_for_scheduling")
    validate_workflow_transition("waiting_for_approval", "waiting_for_approval")


def test_loop_protection_step_count_invariant():
    """State exceeding MAX_WORKFLOW_STEPS (25) raises WorkflowInvariantError."""
    state = {
        "step_count": MAX_WORKFLOW_STEPS + 1,
        "workflow_status": "ready_for_scheduling",
    }
    with pytest.raises(WorkflowInvariantError) as exc:
        validate_workflow_invariants(state)
    assert "Loop protection triggered" in str(exc.value)


def test_appointment_created_invariant():
    """Appointment created status requires non-null service_request_id and appointment_id."""
    # Missing appointment_id
    invalid_state_1 = {
        "workflow_status": "appointment_created",
        "service_request_id": 10,
        "appointment_id": None,
        "step_count": 5,
    }
    with pytest.raises(WorkflowInvariantError):
        validate_workflow_invariants(invalid_state_1)

    # Valid state
    valid_state = {
        "workflow_status": "appointment_created",
        "service_request_id": 10,
        "appointment_id": 99,
        "step_count": 5,
    }
    validate_workflow_invariants(valid_state)


def test_waiting_for_approval_invariant():
    """Waiting for approval requires proposal dict with technician_id and start_time."""
    # Missing proposal
    invalid_state = {
        "workflow_status": "waiting_for_approval",
        "service_request_id": 10,
        "appointment_proposal": None,
        "step_count": 3,
    }
    with pytest.raises(WorkflowInvariantError):
        validate_workflow_invariants(invalid_state)

    # Valid proposal state
    valid_state = {
        "workflow_status": "waiting_for_approval",
        "service_request_id": 10,
        "appointment_proposal": {
            "technician_id": 1,
            "start_time": "2026-09-07T10:00:00+09:00",
        },
        "step_count": 3,
    }
    validate_workflow_invariants(valid_state)


def test_candidate_consistency_invariant():
    """Proposed technician must belong to candidate technician IDs."""
    state = {
        "workflow_status": "waiting_for_approval",
        "service_request_id": 10,
        "candidate_technician_ids": [1, 2],
        "appointment_proposal": {
            "technician_id": 999,  # Not in [1, 2]
            "start_time": "2026-09-07T10:00:00+09:00",
        },
        "step_count": 3,
    }
    with pytest.raises(WorkflowInvariantError) as exc:
        validate_workflow_invariants(state)
    assert "not among eligible candidates" in str(exc.value)
