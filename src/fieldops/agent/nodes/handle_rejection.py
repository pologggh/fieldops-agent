import logging
from typing import Any

from fieldops.agent.state import FieldServiceState
from fieldops.application.appointment_service import AppointmentService
from fieldops.db.session import SessionLocal

logger = logging.getLogger(__name__)


def handle_rejection_node(state: FieldServiceState) -> dict[str, Any]:
    """Node handling operator rejection decision: updates ServiceRequest and records audit log.

    Reads:
        state["service_request_id"]
        state["approval_reason"]

    Returns:
        appointment_id: None
        appointment_status: None
        finalization_status: str
        conflict_detected: bool
        workflow_status: str
    """
    request_id = state.get("request_id")
    service_request_id = state.get("service_request_id")
    reason = state.get("approval_reason")

    logger.info(
        "Node [handle_rejection] started: request_id=%s, service_request_id=%s, reason=%s",
        request_id,
        service_request_id,
        reason,
    )

    if service_request_id:
        with SessionLocal() as session:
            service = AppointmentService(session)
            service.handle_rejection(
                service_request_id=service_request_id,
                reason=reason,
            )

    step_count = state.get("step_count", 0) + 1
    return {
        "step_count": step_count,
        "appointment_id": None,
        "appointment_status": None,
        "finalization_status": "rejected",
        "conflict_detected": False,
        "workflow_status": "rejected",
    }
