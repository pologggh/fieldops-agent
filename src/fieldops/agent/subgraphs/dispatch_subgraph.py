"""Dispatch Subgraph: Technician Matching, Scheduling Availability, and Dispatch Policy Decision."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from fieldops.agent.decisions.decision_result import DecisionAction
from fieldops.agent.decisions.dispatch_decision import evaluate_dispatch_decision
from fieldops.agent.invariants import (
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.nodes.check_schedule import check_schedule_node
from fieldops.agent.nodes.match_technicians import match_technicians_node
from fieldops.agent.state import FieldServiceState
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    WORKFLOW_DECISIONS_TOTAL,
    WORKFLOW_ROUTES_TOTAL,
)

logger = logging.getLogger(__name__)


def dispatch_match_node(state: FieldServiceState) -> dict[str, Any]:
    """Node wrapping technician matching with invariant and step tracking."""
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "service_request_created")
    updates = match_technicians_node(state)
    target_status = updates.get("workflow_status", current_status)
    validate_workflow_transition(current_status, target_status)
    updates["step_count"] = step_count
    updates["current_subgraph"] = "dispatch"
    return updates


def dispatch_schedule_node(state: FieldServiceState) -> dict[str, Any]:
    """Node wrapping schedule availability checking."""
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "ready_for_scheduling")
    updates = check_schedule_node(state)
    target_status = updates.get("workflow_status", current_status)
    validate_workflow_transition(current_status, target_status)
    updates["step_count"] = step_count
    return updates


def dispatch_decision_node(state: FieldServiceState) -> dict[str, Any]:
    """Evaluate matching, scheduling availability, and SLA feasibility."""
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "schedule_options_ready")

    decision = evaluate_dispatch_decision(
        matching_status=state.get("matching_status"),
        candidate_technician_ids=state.get("candidate_technician_ids", []),
        scheduling_status=state.get("scheduling_status"),
        available_options=state.get("available_options", []),
        urgency=state.get("urgency"),
        sla_feasible=True,  # Evaluated by SLA engine
    )

    WORKFLOW_DECISIONS_TOTAL.labels(
        decision_type="dispatch_decision", action=decision.action.value
    ).inc()

    emit_event(
        "workflow.decision_made",
        request_id=state.get("request_id"),
        decision_type="dispatch_decision",
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
        if current_status not in (
            "no_technician_available",
            "no_available_slots",
            "needs_location",
            "needs_skill_information",
        ):
            validate_workflow_transition(current_status, "escalated")
            updates["workflow_status"] = "escalated"
        updates["escalation_details"] = decision.to_dict()

    return updates


def route_after_dispatch_match(state: FieldServiceState) -> str:
    """Route based on technician matching outcome."""
    status = state.get("workflow_status")
    if status == "ready_for_scheduling":
        WORKFLOW_ROUTES_TOTAL.labels(
            from_stage="dispatch_match", to_route="dispatch_schedule"
        ).inc()
        return "dispatch_schedule"
    if status in ("no_technician_available", "no_candidates", "needs_location", "needs_skill_information"):
        WORKFLOW_ROUTES_TOTAL.labels(
            from_stage="dispatch_match", to_route="dispatch_decision"
        ).inc()
        return "dispatch_decision"
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="dispatch_match", to_route="end").inc()
    return END


def route_after_dispatch_schedule(state: FieldServiceState) -> str:
    """Route after schedule checking to decision."""
    status = state.get("workflow_status")
    if status in ("schedule_options_ready", "no_available_slots", "needs_time_clarification"):
        WORKFLOW_ROUTES_TOTAL.labels(
            from_stage="dispatch_schedule", to_route="dispatch_decision"
        ).inc()
        return "dispatch_decision"
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="dispatch_schedule", to_route="end").inc()
    return END


def build_dispatch_subgraph():
    """Build and compile the Dispatch Subgraph."""
    graph = StateGraph(FieldServiceState)
    graph.add_node("dispatch_match", dispatch_match_node)
    graph.add_node("dispatch_schedule", dispatch_schedule_node)
    graph.add_node("dispatch_decision", dispatch_decision_node)

    graph.add_edge(START, "dispatch_match")
    graph.add_conditional_edges(
        "dispatch_match",
        route_after_dispatch_match,
        {
            "dispatch_schedule": "dispatch_schedule",
            "dispatch_decision": "dispatch_decision",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "dispatch_schedule",
        route_after_dispatch_schedule,
        {"dispatch_decision": "dispatch_decision", END: END},
    )
    graph.add_edge("dispatch_decision", END)

    return graph.compile()
