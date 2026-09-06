"""Approval Subgraph: Proposal Construction, Tiered Policy Evaluation, and Multi-Level HITL Interrupt."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from fieldops.agent.decisions.approval_decision import (
    evaluate_proposal_approval_level,
    evaluate_resume_approval_decision,
)
from fieldops.agent.decisions.decision_result import (
    DecisionAction,
    HumanReviewLevel,
    ReasonCode,
)
from fieldops.agent.invariants import (
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.nodes.build_appointment_proposal import (
    build_appointment_proposal_node,
)
from fieldops.agent.state import FieldServiceState
from fieldops.core.exceptions import WorkflowStateError
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    WORKFLOW_DECISIONS_TOTAL,
    WORKFLOW_HUMAN_REVIEWS_TOTAL,
    WORKFLOW_ROUTES_TOTAL,
)

logger = logging.getLogger(__name__)


def approval_proposal_node(state: FieldServiceState) -> dict[str, Any]:
    """Construct proposal and evaluate ApprovalPolicy to determine required reviewer role."""
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "schedule_options_ready")

    updates = build_appointment_proposal_node(state)
    target_status = updates.get("workflow_status", current_status)
    validate_workflow_transition(current_status, target_status)

    proposal = updates.get("appointment_proposal")
    if proposal:
        policy_decision = evaluate_proposal_approval_level(
            urgency=state.get("urgency"),
            start_time=proposal.get("start_time"),
            end_time=proposal.get("end_time"),
            reschedule_count=state.get("reschedule_count", 0),
        )
        updates["human_review_level"] = policy_decision.required_role.value
        updates["last_decision"] = policy_decision.to_dict()

        history = list(state.get("decision_history", []))
        history.append(policy_decision.to_dict())
        updates["decision_history"] = history

        WORKFLOW_HUMAN_REVIEWS_TOTAL.labels(
            review_level=policy_decision.required_role.value,
            review_type="appointment_proposal",
        ).inc()

        emit_event(
            "workflow.human_review_required",
            request_id=state.get("request_id"),
            required_level=policy_decision.required_role.value,
            reason_code=policy_decision.reason_code,
            policy_version=policy_decision.policy_version,
        )

    updates["step_count"] = step_count
    updates["current_subgraph"] = "approval"
    return updates


def approval_review_node(state: FieldServiceState) -> dict[str, Any]:
    """Execute LangGraph interrupt and evaluate operator/admin resume action."""
    request_id = state.get("request_id")
    proposal = state.get("appointment_proposal")
    service_request_id = state.get("service_request_id")
    required_role_str = state.get("human_review_level", "operator")
    required_role = (
        HumanReviewLevel(required_role_str)
        if required_role_str in HumanReviewLevel._value2member_map_
        else HumanReviewLevel.OPERATOR
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
        subgraph="approval",
        required_role=required_role.value,
    )

    decision_data: dict[str, Any] = interrupt(interrupt_payload)

    # Workflow has resumed
    decision_val = (
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

    emit_event(
        "workflow.resume",
        request_id=request_id,
        decision=decision_val,
        actor_role=actor_role,
    )

    # Enforce role hierarchy on resumption
    decision_outcome = evaluate_resume_approval_decision(
        decision=decision_val,
        reason=reason,
        actor_role=actor_role,
        required_role=required_role,
    )

    WORKFLOW_DECISIONS_TOTAL.labels(
        decision_type="approval_decision", action=decision_outcome.action.value
    ).inc()

    if decision_outcome.reason_code == "INSUFFICIENT_ROLE_PRIVILEGES":
        raise WorkflowStateError(decision_outcome.reason)

    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "waiting_for_approval")

    history = list(state.get("decision_history", []))
    history.append(decision_outcome.to_dict())

    if decision_outcome.action == DecisionAction.FINALIZE:
        validate_workflow_transition(current_status, "approval_completed")
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
        return {
            "approval_status": "rejected",
            "approval_reason": reason,
            "workflow_status": "rejected",
            "step_count": step_count,
            "last_decision": decision_outcome.to_dict(),
            "decision_history": history,
        }


def route_after_approval_proposal(state: FieldServiceState) -> str:
    """Route after proposal construction to review interrupt."""
    status = state.get("workflow_status")
    if status == "waiting_for_approval":
        WORKFLOW_ROUTES_TOTAL.labels(
            from_stage="approval_proposal", to_route="approval_review"
        ).inc()
        return "approval_review"
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="approval_proposal", to_route="end").inc()
    return END


def build_approval_subgraph():
    """Build and compile the Approval Subgraph."""
    graph = StateGraph(FieldServiceState)
    graph.add_node("approval_proposal", approval_proposal_node)
    graph.add_node("approval_review", approval_review_node)

    graph.add_edge(START, "approval_proposal")
    graph.add_conditional_edges(
        "approval_proposal",
        route_after_approval_proposal,
        {"approval_review": "approval_review", END: END},
    )
    graph.add_edge("approval_review", END)

    return graph.compile()
