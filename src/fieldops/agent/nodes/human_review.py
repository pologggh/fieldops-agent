import logging
from typing import Any

from langgraph.types import interrupt

from fieldops.agent.decisions.approval_decision import (
    evaluate_resume_approval_decision,
)
from fieldops.agent.decisions.decision_result import (
    DecisionAction,
    HumanReviewLevel,
)
from fieldops.agent.invariants import validate_workflow_transition
from fieldops.agent.state import FieldServiceState
from fieldops.core.exceptions import WorkflowStateError
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import WORKFLOW_DECISIONS_TOTAL

logger = logging.getLogger(__name__)


def human_review_node(state: FieldServiceState) -> dict[str, Any]:
    """Node implementing Tiered Human-in-the-loop (HITL) review for appointment proposals.

    Workflow execution pauses here via LangGraph's native interrupt() mechanism.
    The current execution state is checkpointed, and proposal details and required role
    are yielded to the operator/admin for review.

    When resumed via Command(resume={"decision": "approve" | "reject", "reason": ..., "actor_role": ...}):
    - Enforces that actor_role has sufficient privileges for state["human_review_level"]
    - 'approve': updates approval_status='approved', workflow_status='approval_completed'
    - 'reject': updates approval_status='rejected', approval_reason=reason, workflow_status='rejected'
    """
    request_id = state.get("request_id")
    proposal = state.get("appointment_proposal")
    service_request_id = state.get("service_request_id")
    required_role_str = state.get("human_review_level", "operator")
    required_role = (
        HumanReviewLevel(required_role_str)
        if required_role_str in HumanReviewLevel._value2member_map_
        else HumanReviewLevel.OPERATOR
    )

    logger.info(
        "Workflow interrupted at [human_review]: request_id=%s, service_request_id=%s, required_role=%s",
        request_id,
        service_request_id,
        required_role.value,
    )

    # Yield operator review payload and suspend execution
    interrupt_payload = {
        "request_id": request_id,
        "service_request_id": service_request_id,
        "workflow_status": "waiting_for_approval",
        "appointment_proposal": proposal,
        "required_role": required_role.value,
    }

    emit_event(
        "workflow.interrupt",
        request_id=request_id,
        service_request_id=service_request_id,
        required_role=required_role.value,
    )

    decision_data: dict[str, Any] = interrupt(interrupt_payload)

    # Workflow has resumed
    decision = (
        decision_data.get("decision")
        if isinstance(decision_data, dict)
        else str(decision_data)
    )
    reason = decision_data.get("reason") if isinstance(decision_data, dict) else None
    actor_role = (
        decision_data.get("actor_role", "operator")
        if isinstance(decision_data, dict)
        else "operator"
    )

    logger.info(
        "Workflow resumed at [human_review]: request_id=%s, decision=%s, actor_role=%s",
        request_id,
        decision,
        actor_role,
    )

    emit_event(
        "workflow.resume",
        request_id=request_id,
        decision=decision,
        actor_role=actor_role,
    )

    # Re-verify authorization privileges on resumption
    decision_outcome = evaluate_resume_approval_decision(
        decision=decision,
        reason=reason,
        actor_role=actor_role,
        required_role=required_role,
    )

    WORKFLOW_DECISIONS_TOTAL.labels(
        decision_type="resume_approval", action=decision_outcome.action.value
    ).inc()

    if decision_outcome.reason_code == "INSUFFICIENT_ROLE_PRIVILEGES":
        logger.warning(
            "Resume denied due to insufficient privileges: actor_role=%s, required=%s",
            actor_role,
            required_role.value,
        )
        raise WorkflowStateError(decision_outcome.reason)

    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "waiting_for_approval")

    history = list(state.get("decision_history", []))
    history.append(decision_outcome.to_dict())

    if decision_outcome.action == DecisionAction.FINALIZE:
        validate_workflow_transition(current_status, "approval_completed")
        logger.info("Proposal approved by %s for request_id=%s", actor_role, request_id)
        return {
            "approval_status": "approved",
            "approval_reason": reason,
            "workflow_status": "approval_completed",
            "step_count": step_count,
            "last_decision": decision_outcome.to_dict(),
            "decision_history": history,
        }
    else:
        validate_workflow_transition(current_status, "rejected")
        logger.info(
            "Proposal rejected by %s for request_id=%s, reason=%s",
            actor_role,
            request_id,
            reason,
        )
        return {
            "approval_status": "rejected",
            "approval_reason": reason,
            "workflow_status": "rejected",
            "step_count": step_count,
            "last_decision": decision_outcome.to_dict(),
            "decision_history": history,
        }
