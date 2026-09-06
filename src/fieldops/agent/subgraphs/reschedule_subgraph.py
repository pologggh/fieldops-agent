"""Reschedule Subgraph: Automated Rescheduling, Loop Bounding, and Escalation Routing."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from fieldops.agent.decisions.decision_result import DecisionAction, ReasonCode
from fieldops.agent.decisions.policies import EscalationPolicy
from fieldops.agent.invariants import (
    MAX_RESCHEDULE_COUNT,
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.state import FieldServiceState
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    WORKFLOW_DECISIONS_TOTAL,
    WORKFLOW_ROUTES_TOTAL,
)

logger = logging.getLogger(__name__)


def reschedule_evaluate_node(state: FieldServiceState) -> dict[str, Any]:
    """Evaluate reschedule loop bounds and prepare state for redispatch or escalation."""
    step_count = state.get("step_count", 0) + 1
    reschedule_count = state.get("reschedule_count", 0)
    current_status = state.get("workflow_status", "needs_rescheduling")

    if reschedule_count >= MAX_RESCHEDULE_COUNT:
        # Loop limit reached: route to human escalation
        esc = EscalationPolicy.evaluate(
            trigger_reason="reschedule_limit",
            urgency=state.get("urgency"),
            reschedule_count=reschedule_count,
        )
        validate_workflow_transition(current_status, "escalated")

        WORKFLOW_DECISIONS_TOTAL.labels(
            decision_type="reschedule_decision", action=DecisionAction.ESCALATE.value
        ).inc()

        emit_event(
            "workflow.decision_made",
            request_id=state.get("request_id"),
            decision_type="reschedule_decision",
            action=DecisionAction.ESCALATE.value,
            reason_code=ReasonCode.RESCHEDULE_LIMIT_EXCEEDED,
            policy_version=esc["policy_version"],
        )

        return {
            "step_count": step_count,
            "workflow_status": "escalated",
            "escalation_details": {
                "action": DecisionAction.ESCALATE.value,
                "reason_code": ReasonCode.RESCHEDULE_LIMIT_EXCEEDED,
                "reason": esc["reason"],
                "required_role": esc["required_role"].value,
                "reschedule_count": reschedule_count,
            },
            "current_subgraph": "reschedule",
        }

    # Within bounds: increment count and reset scheduling options for redispatch
    new_count = reschedule_count + 1
    validate_workflow_transition(current_status, "ready_for_scheduling")

    WORKFLOW_DECISIONS_TOTAL.labels(
        decision_type="reschedule_decision", action=DecisionAction.RESCHEDULE.value
    ).inc()

    emit_event(
        "workflow.reschedule_attempted",
        request_id=state.get("request_id"),
        reschedule_count=new_count,
    )

    return {
        "step_count": step_count,
        "reschedule_count": new_count,
        "workflow_status": "ready_for_scheduling",
        "appointment_proposal": None,
        "scheduling_status": None,
        "available_options": [],
        "conflict_detected": False,
        "current_subgraph": "reschedule",
    }


def build_reschedule_subgraph():
    """Build and compile the Reschedule Subgraph."""
    graph = StateGraph(FieldServiceState)
    graph.add_node("reschedule_evaluate", reschedule_evaluate_node)

    graph.add_edge(START, "reschedule_evaluate")
    graph.add_edge("reschedule_evaluate", END)

    return graph.compile()
