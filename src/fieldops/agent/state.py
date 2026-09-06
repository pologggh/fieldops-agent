"""Workflow state definition for the FieldOps service request processing pipeline (Phase 28)."""

from typing import Any, TypedDict


class FieldServiceState(TypedDict, total=False):
    """Workflow state for the FieldOps service request processing pipeline."""

    # 1. Base Request & Customer Identification
    request_id: str
    customer_name: str
    customer_email: str
    customer_phone: str | None
    raw_message: str
    service_type: str | None
    urgency: str | None
    location: str | None
    required_skills: list[str]
    preferred_time: str | None
    problem_description: str | None
    customer_id: int | None
    service_request_id: int | None

    # 2. Matching & Scheduling Data
    candidate_technician_ids: list[int]
    matching_status: str | None
    requested_window_start: str | None
    requested_window_end: str | None
    available_options: list[dict[str, Any]]
    scheduling_status: str | None

    # 3. Proposal & Human Review (HITL)
    appointment_proposal: dict[str, Any] | None
    approval_status: str | None
    approval_reason: str | None
    human_review_required: bool
    human_review_level: str  # "none", "operator", "senior_operator", "admin"

    # 4. Finalization & Appointments
    appointment_id: int | None
    appointment_status: str | None
    finalization_status: str | None
    conflict_detected: bool

    # 5. Validation & Failure Handling
    validation_errors: list[str]
    error_code: str | None
    error_message: str | None
    failed_step: str | None
    retryable: bool
    workflow_status: str

    # 6. Source & Inbound Tracking
    source: str | None
    inbound_event_id: int | None

    # 7. Phase 28: Loop Protection Counters
    step_count: int
    clarification_count: int
    reschedule_count: int
    retry_count: int
    retry_budget: int

    # 8. Phase 28: Decision & Explainability Layer
    last_decision: dict[str, Any] | None
    decision_history: list[dict[str, Any]]
    current_subgraph: str | None

    # 9. Phase 28: Auxiliary Integration Recovery & Compensation
    integration_status: str | None  # "synced", "recovery_required", "failed", None
    escalation_details: dict[str, Any] | None
    compensation_details: dict[str, Any] | None

    # 10. Phase 28: Observability Durations
    active_duration_s: float
    waiting_duration_s: float


def create_initial_state(
    request_id: str,
    raw_message: str,
    customer_name: str = "",
    customer_email: str = "",
    customer_phone: str | None = None,
    source: str | None = None,
    inbound_event_id: int | None = None,
) -> FieldServiceState:
    """Create a clean, initialized FieldServiceState dictionary with backwards-compatible defaults."""
    return {
        "request_id": request_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "raw_message": raw_message,
        "service_type": None,
        "urgency": None,
        "location": None,
        "required_skills": [],
        "preferred_time": None,
        "problem_description": None,
        "customer_id": None,
        "service_request_id": None,
        "candidate_technician_ids": [],
        "matching_status": None,
        "requested_window_start": None,
        "requested_window_end": None,
        "available_options": [],
        "scheduling_status": None,
        "appointment_proposal": None,
        "approval_status": None,
        "approval_reason": None,
        "human_review_required": False,
        "human_review_level": "none",
        "appointment_id": None,
        "appointment_status": None,
        "finalization_status": None,
        "conflict_detected": False,
        "validation_errors": [],
        "error_code": None,
        "error_message": None,
        "failed_step": None,
        "retryable": False,
        "workflow_status": "pending",
        "source": source,
        "inbound_event_id": inbound_event_id,
        # Phase 28 fields
        "step_count": 0,
        "clarification_count": 0,
        "reschedule_count": 0,
        "retry_count": 0,
        "retry_budget": 3,
        "last_decision": None,
        "decision_history": [],
        "current_subgraph": "intake",
        "integration_status": None,
        "escalation_details": None,
        "compensation_details": None,
        "active_duration_s": 0.0,
        "waiting_duration_s": 0.0,
    }
