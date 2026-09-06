"""Escalation Subgraph: Structured Human Escalation, Reason Classification, and Audit Attribution."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from fieldops.agent.decisions.decision_result import ReasonCode
from fieldops.agent.invariants import validate_workflow_transition
from fieldops.agent.state import FieldServiceState
from fieldops.core.logging import emit_event
from fieldops.db.session import SessionLocal
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.service_request_repository import ServiceRequestRepository

logger = logging.getLogger(__name__)


def escalation_node(state: FieldServiceState) -> dict[str, Any]:
    """Formalize workflow escalation, record audit logs, and notify operations."""
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "pending")
    target_status = (
        current_status
        if current_status in ("no_technician_available", "no_available_slots", "needs_location", "needs_skill_information")
        else "escalated"
    )
    validate_workflow_transition(current_status, target_status)

    details = state.get("escalation_details") or state.get("last_decision") or {}
    reason_code = details.get("reason_code", ReasonCode.NO_AVAILABLE_SLOTS)
    reason = details.get("reason", "Workflow routed to human operations queue.")
    service_request_id = state.get("service_request_id")

    # Update database record and write audit log if service_request_id exists
    if service_request_id:
        try:
            with SessionLocal() as session:
                audit_repo = AuditLogRepository(session)

                audit_repo.create(
                    entity_type="service_request",
                    entity_id=service_request_id,
                    action="workflow.escalated",
                    details={
                        "reason_code": reason_code,
                        "reason": reason,
                        "required_role": details.get("required_role", "operator"),
                        "severity": details.get("severity", "P1"),
                        "step_count": step_count,
                    },
                )
                session.commit()
        except Exception as e:
            logger.error("Failed to update ServiceRequest during escalation: %s", e)

    emit_event(
        "workflow.escalated",
        request_id=state.get("request_id"),
        service_request_id=service_request_id,
        reason_code=reason_code,
        reason=reason,
    )

    return {
        "step_count": step_count,
        "workflow_status": target_status,
        "current_subgraph": "escalation",
    }


def build_escalation_subgraph():
    """Build and compile the Escalation Subgraph."""
    graph = StateGraph(FieldServiceState)
    graph.add_node("escalation_process", escalation_node)

    graph.add_edge(START, "escalation_process")
    graph.add_edge("escalation_process", END)

    return graph.compile()
