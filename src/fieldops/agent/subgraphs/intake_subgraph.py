"""Intake Subgraph: Parsing, Validation, Clarification Bounding, and Service Request Persistence."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from fieldops.agent.decisions.decision_result import DecisionAction, ReasonCode
from fieldops.agent.decisions.request_decision import evaluate_request_intake_decision
from fieldops.agent.invariants import (
    MAX_CLARIFICATION_COUNT,
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.nodes.parse_request import parse_request_node
from fieldops.agent.nodes.persist_service_request import persist_service_request_node
from fieldops.agent.nodes.validate_request import validate_request_node
from fieldops.agent.state import FieldServiceState
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    WORKFLOW_DECISIONS_TOTAL,
    WORKFLOW_ROUTES_TOTAL,
)

logger = logging.getLogger(__name__)


def intake_parse_node(state: FieldServiceState) -> dict[str, Any]:
    """Node wrapping request parsing with step counter increment."""
    step_count = state.get("step_count", 0) + 1
    updates = parse_request_node(state)
    target_status = updates.get("workflow_status", state.get("workflow_status", "pending"))
    validate_workflow_transition(state.get("workflow_status", "pending"), target_status)
    updates["step_count"] = step_count
    updates["current_subgraph"] = "intake"
    return updates


def intake_validate_node(state: FieldServiceState) -> dict[str, Any]:
    """Node wrapping validation and transition validation."""
    step_count = state.get("step_count", 0) + 1
    updates = validate_request_node(state)
    target_status = updates.get("workflow_status", state.get("workflow_status", "parsed"))
    validate_workflow_transition(state.get("workflow_status", "parsed"), target_status)
    updates["step_count"] = step_count
    return updates


def intake_decision_node(state: FieldServiceState) -> dict[str, Any]:
    """Evaluate intake completion and enforce clarification loop protection."""
    step_count = state.get("step_count", 0) + 1
    clarification_count = state.get("clarification_count", 0)
    current_status = state.get("workflow_status", "validated")

    decision = evaluate_request_intake_decision(
        workflow_status=current_status,
        validation_errors=state.get("validation_errors", []),
        service_type=state.get("service_type"),
        urgency=state.get("urgency"),
        location=state.get("location"),
        clarification_count=clarification_count,
    )

    WORKFLOW_DECISIONS_TOTAL.labels(
        decision_type="intake_decision", action=decision.action.value
    ).inc()

    emit_event(
        "workflow.decision_made",
        request_id=state.get("request_id"),
        decision_type="intake_decision",
        action=decision.action.value,
        reason_code=decision.reason_code,
        policy_version=decision.policy_version,
    )

    history = list(state.get("decision_history", []))
    history.append(decision.to_dict())

    updates: dict[str, Any] = {
        "step_count": step_count,
        "last_decision": decision.to_dict(),
        "decision_history": history,
    }

    if decision.action == DecisionAction.ESCALATE:
        validate_workflow_transition(current_status, "escalated")
        updates["workflow_status"] = "escalated"
        updates["escalation_details"] = decision.to_dict()
    elif decision.action == DecisionAction.ASK_FOR_INFORMATION:
        # Increment clarification counter
        updates["clarification_count"] = clarification_count + 1
        validate_workflow_transition(current_status, "needs_information")
        updates["workflow_status"] = "needs_information"

    return updates


def intake_persist_node(state: FieldServiceState) -> dict[str, Any]:
    """Node persisting customer and service request upon valid completion."""
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "validated")
    validate_workflow_transition(current_status, "service_request_created")
    updates = persist_service_request_node(state)
    updates["step_count"] = step_count
    return updates


def route_after_intake_parse(state: FieldServiceState) -> str:
    """Route based on parsing status."""
    status = state.get("workflow_status")
    if status == "parsed":
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="intake_parse", to_route="intake_validate").inc()
        return "intake_validate"
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="intake_parse", to_route="end").inc()
    return END


def route_after_intake_decision(state: FieldServiceState) -> str:
    """Route based on intake decision: persist vs end/clarify vs escalate."""
    status = state.get("workflow_status")
    decision = state.get("last_decision") or {}
    action = decision.get("action")

    if action == DecisionAction.DISPATCH.value:
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="intake_decision", to_route="intake_persist").inc()
        return "intake_persist"
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="intake_decision", to_route="end").inc()
    return END


def build_intake_subgraph():
    """Build and compile the Intake Subgraph."""
    graph = StateGraph(FieldServiceState)
    graph.add_node("intake_parse", intake_parse_node)
    graph.add_node("intake_validate", intake_validate_node)
    graph.add_node("intake_decision", intake_decision_node)
    graph.add_node("intake_persist", intake_persist_node)

    graph.add_edge(START, "intake_parse")
    graph.add_conditional_edges(
        "intake_parse",
        route_after_intake_parse,
        {"intake_validate": "intake_validate", END: END},
    )
    graph.add_edge("intake_validate", "intake_decision")
    graph.add_conditional_edges(
        "intake_decision",
        route_after_intake_decision,
        {"intake_persist": "intake_persist", END: END},
    )
    graph.add_edge("intake_persist", END)

    return graph.compile()
