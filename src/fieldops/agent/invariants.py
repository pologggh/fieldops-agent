"""Workflow Invariants and State Transition Guard Engine for Phase 28."""

import logging
from typing import Any

from fieldops.core.exceptions import WorkflowInvariantError

logger = logging.getLogger(__name__)

# Workflow execution thresholds and loop guards
MAX_WORKFLOW_STEPS = 25
MAX_CLARIFICATION_COUNT = 3
MAX_RESCHEDULE_COUNT = 3
MAX_RETRY_BUDGET = 3

# Authoritative Allowed Transition Table
# Maps current workflow_status -> set of valid target workflow_statuses
VALID_WORKFLOW_TRANSITIONS: dict[str, set[str]] = {
    "pending": {
        "parsed",
        "llm_failed",
        "needs_information",
        "service_request_created",
        "ready_for_scheduling",
        "schedule_options_ready",
        "waiting_for_approval",
        "no_available_slots",
        "approval_completed",
        "escalated",
        "no_technician_available",
        "failed",
        "stopped",
    },
    "parsed": {
        "validated",
        "needs_information",
        "failed",
        "stopped",
    },
    "validated": {
        "ready_for_service_request",
        "service_request_created",
        "needs_information",
        "failed",
        "stopped",
    },
    "ready_for_service_request": {
        "service_request_created",
        "needs_information",
        "failed",
        "stopped",
    },
    "needs_information": {
        "parsed",
        "escalated",
        "failed",
        "stopped",
    },
    "service_request_created": {
        "ready_for_scheduling",
        "needs_location",
        "needs_skill_information",
        "no_technician_available",
        "escalated",
        "failed",
        "stopped",
    },
    "needs_location": {
        "ready_for_scheduling",
        "needs_information",
        "escalated",
        "failed",
        "stopped",
    },
    "needs_skill_information": {
        "ready_for_scheduling",
        "needs_information",
        "escalated",
        "failed",
        "stopped",
    },
    "no_technician_available": {
        "ready_for_scheduling",
        "needs_information",
        "escalated",
        "failed",
        "stopped",
    },
    "ready_for_scheduling": {
        "schedule_options_ready",
        "no_available_slots",
        "needs_time_clarification",
        "escalated",
        "failed",
        "stopped",
    },
    "needs_time_clarification": {
        "ready_for_scheduling",
        "needs_information",
        "escalated",
        "failed",
        "stopped",
    },
    "no_available_slots": {
        "ready_for_scheduling",
        "needs_rescheduling",
        "escalated",
        "failed",
        "stopped",
    },
    "schedule_options_ready": {
        "waiting_for_approval",
        "no_available_slots",
        "escalated",
        "failed",
        "stopped",
    },
    "waiting_for_approval": {
        "approval_completed",
        "rejected",
        "needs_rescheduling",
        "escalated",
        "failed",
        "stopped",
    },
    "approval_completed": {
        "appointment_created",
        "needs_rescheduling",
        "failed",
        "stopped",
    },
    "needs_rescheduling": {
        "ready_for_scheduling",
        "service_request_created",
        "escalated",
        "failed",
        "stopped",
    },
    "escalated": {
        "waiting_for_approval",
        "ready_for_scheduling",
        "service_request_created",
        "rejected",
        "completed",
        "failed",
        "stopped",
    },
    "appointment_created": {
        "in_progress",
        "completed",
        "needs_rescheduling",
        "cancelled",
        "failed",
        "stopped",
    },
    "in_progress": {
        "completed",
        "cancelled",
        "failed",
    },
    "rejected": {
        "closed",
        "archived",
    },
    "llm_failed": {
        "parsed",
        "escalated",
        "failed",
        "stopped",
    },
    # Terminal statuses (cannot transition to active stages)
    "completed": set(),
    "cancelled": set(),
    "closed": set(),
    "archived": set(),
    "failed": set(),
    "stopped": set(),
}


def validate_workflow_transition(current_status: str, target_status: str) -> None:
    """Enforce state transition guard rules.

    Raises:
        WorkflowInvariantError: If the transition is illegal according to VALID_WORKFLOW_TRANSITIONS.
    """
    # Self-transition / re-entrant execution is permissible
    if current_status == target_status:
        return

    allowed_targets = VALID_WORKFLOW_TRANSITIONS.get(current_status)
    if allowed_targets is None:
        raise WorkflowInvariantError(
            f"Unregistered source workflow status: '{current_status}'. Transition to '{target_status}' forbidden."
        )

    if target_status not in allowed_targets:
        logger.error(
            "State transition guard rejected illegal transition: '%s' -> '%s'",
            current_status,
            target_status,
        )
        raise WorkflowInvariantError(
            f"Illegal workflow state transition: cannot transition from '{current_status}' to '{target_status}'. "
            f"Allowed target states: {sorted(allowed_targets) if allowed_targets else 'None (Terminal State)'}"
        )


def validate_workflow_invariants(state: dict[str, Any]) -> None:
    """Verify business and execution integrity invariants across the workflow state.

    Raises:
        WorkflowInvariantError: When any invariant condition is breached.
    """
    status = state.get("workflow_status", "pending")
    step_count = state.get("step_count", 0)

    # Invariant 1: Step counter must not exceed global threshold (Loop Protection)
    if step_count > MAX_WORKFLOW_STEPS:
        raise WorkflowInvariantError(
            f"Loop protection triggered: workflow execution step count ({step_count}) exceeded MAX_WORKFLOW_STEPS ({MAX_WORKFLOW_STEPS})."
        )

    # Invariant 2: Appointment creation invariant
    if status == "appointment_created":
        if not state.get("service_request_id"):
            raise WorkflowInvariantError(
                "Invariant violated: status is 'appointment_created' but 'service_request_id' is missing."
            )
        if not state.get("appointment_id"):
            raise WorkflowInvariantError(
                "Invariant violated: status is 'appointment_created' but 'appointment_id' is missing."
            )

    # Invariant 3: Waiting for approval invariant
    if status == "waiting_for_approval":
        if not state.get("service_request_id"):
            raise WorkflowInvariantError(
                "Invariant violated: status is 'waiting_for_approval' but 'service_request_id' is missing."
            )
        proposal = state.get("appointment_proposal")
        if not proposal or not isinstance(proposal, dict):
            raise WorkflowInvariantError(
                "Invariant violated: status is 'waiting_for_approval' but 'appointment_proposal' is missing or malformed."
            )
        if not proposal.get("technician_id") or not proposal.get("start_time"):
            raise WorkflowInvariantError(
                "Invariant violated: 'appointment_proposal' lacks essential technician_id or start_time."
            )

    # Invariant 4: Candidate consistency check
    proposal = state.get("appointment_proposal")
    candidates = state.get("candidate_technician_ids", [])
    if proposal and candidates:
        tech_id = proposal.get("technician_id")
        if tech_id and tech_id not in candidates:
            raise WorkflowInvariantError(
                f"Invariant violated: proposed technician_id ({tech_id}) is not among eligible candidates ({candidates})."
            )

    # Invariant 5: Completed state invariant
    if status == "completed":
        if not state.get("appointment_id") and not state.get("service_request_id"):
            raise WorkflowInvariantError(
                "Invariant violated: workflow is 'completed' but lacks reference entity IDs."
            )
