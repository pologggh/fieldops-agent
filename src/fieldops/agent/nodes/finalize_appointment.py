import logging
from typing import Any

from fieldops.agent.invariants import (
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.state import FieldServiceState
from fieldops.application.appointment_service import AppointmentService
from fieldops.core.logging import emit_event
from fieldops.db.session import SessionLocal

logger = logging.getLogger(__name__)


def finalize_appointment_node(state: FieldServiceState) -> dict[str, Any]:
    """Node executing atomic appointment creation, conflict re-check, and audit logging.

    Only invoked after operator approval.

    Reads:
        state["service_request_id"]
        state["appointment_proposal"]

    Returns:
        appointment_id: int | None
        appointment_status: str | None
        finalization_status: str
        conflict_detected: bool
        workflow_status: str
        step_count: int
        integration_status: str
    """
    request_id = state.get("request_id")
    proposal = state.get("appointment_proposal")
    service_request_id = state.get("service_request_id")
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "approval_completed")

    logger.info(
        "Node [finalize_appointment] started: request_id=%s, service_request_id=%s",
        request_id,
        service_request_id,
    )

    if not proposal or not service_request_id:
        logger.error(
            "Cannot finalize appointment: missing proposal or service_request_id for request_id=%s",
            request_id,
        )
        validate_workflow_transition(current_status, "needs_rescheduling")
        return {
            "step_count": step_count,
            "appointment_id": None,
            "appointment_status": None,
            "finalization_status": "error",
            "conflict_detected": False,
            "workflow_status": "needs_rescheduling",
        }

    with SessionLocal() as session:
        service = AppointmentService(session)
        result = service.finalize_appointment(
            service_request_id=service_request_id,
            technician_id=proposal["technician_id"],
            start_time=proposal["start_time"],
            end_time=proposal["end_time"],
        )

    if result.success:
        workflow_status = "appointment_created"
        integration_status = state.get("integration_status") or "synced"
    elif result.conflict_detected:
        workflow_status = "needs_rescheduling"
        integration_status = None
    else:
        workflow_status = "failed"
        integration_status = None

    validate_workflow_transition(current_status, workflow_status)

    logger.info(
        "Node [finalize_appointment] completed: request_id=%s, appointment_id=%s, conflict=%s, workflow_status=%s",
        request_id,
        result.appointment_id,
        result.conflict_detected,
        workflow_status,
    )

    updates = {
        "step_count": step_count,
        "appointment_id": result.appointment_id,
        "appointment_status": result.appointment_status,
        "finalization_status": result.finalization_status,
        "conflict_detected": result.conflict_detected,
        "workflow_status": workflow_status,
        "integration_status": integration_status,
    }

    if result.success and result.appointment_id:
        emit_event(
            "workflow.appointment_finalized",
            request_id=request_id,
            service_request_id=service_request_id,
            appointment_id=result.appointment_id,
            integration_status=integration_status,
        )
        # Validate post-creation invariants
        merged_state = {**state, **updates}
        validate_workflow_invariants(merged_state)

    return updates
