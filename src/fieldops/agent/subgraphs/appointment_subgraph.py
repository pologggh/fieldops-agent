"""Appointment Subgraph: Conflict Re-check, Transactional Creation, Outbox, and Core Success Guarantees."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from fieldops.agent.decisions.compensation import CompensationEngine
from fieldops.agent.decisions.decision_result import DecisionAction, ReasonCode
from fieldops.agent.invariants import (
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.nodes.finalize_appointment import finalize_appointment_node
from fieldops.agent.state import FieldServiceState
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    WORKFLOW_DECISIONS_TOTAL,
    WORKFLOW_ROUTES_TOTAL,
)

logger = logging.getLogger(__name__)


def appointment_finalize_node(state: FieldServiceState) -> dict[str, Any]:
    """Execute atomic appointment creation and enforce Core Business Fact invariants."""
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "approval_completed")

    updates = finalize_appointment_node(state)
    target_status = updates.get("workflow_status", current_status)
    validate_workflow_transition(current_status, target_status)

    updates["step_count"] = step_count
    updates["current_subgraph"] = "appointment"

    # Evaluate Core Success + Auxiliary Integration Status
    if updates.get("appointment_id") and target_status == "appointment_created":
        # Core appointment succeeded. External integrations (Calendar/Email) are handled via Outbox.
        # By default in transactional outbox architecture, the integration status is 'synced' or 'recovery_required'
        updates["integration_status"] = state.get("integration_status") or "synced"

        emit_event(
            "workflow.appointment_finalized",
            request_id=state.get("request_id"),
            appointment_id=updates["appointment_id"],
            integration_status=updates["integration_status"],
        )

        # Invariant check on appointment created
        merged_state = {**state, **updates}
        validate_workflow_invariants(merged_state)

    return updates


def build_appointment_subgraph():
    """Build and compile the Appointment Subgraph."""
    graph = StateGraph(FieldServiceState)
    graph.add_node("appointment_finalize", appointment_finalize_node)

    graph.add_edge(START, "appointment_finalize")
    graph.add_edge("appointment_finalize", END)

    return graph.compile()
