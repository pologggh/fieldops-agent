"""Main FieldOps Stateful Workflow with Dynamic Routing, Subgraphs, and Tiered HITL (Phase 28)."""

import logging
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from fieldops.agent.checkpointer import get_checkpointer
from fieldops.agent.invariants import (
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.nodes import (
    build_appointment_proposal_node,
    handle_rejection_node,
    human_review_node,
)
from fieldops.agent.state import FieldServiceState
from fieldops.agent.subgraphs import (
    build_appointment_subgraph,
    build_dispatch_subgraph,
    build_escalation_subgraph,
    build_intake_subgraph,
    build_reschedule_subgraph,
)
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    WORKFLOW_DEAD_ENDS_TOTAL,
    WORKFLOW_ROUTES_TOTAL,
)
from fieldops.observability.tracing import trace_node

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Dynamic Routing Evaluators
# ==============================================================================


def route_after_intake(
    state: FieldServiceState,
) -> Literal["dispatch_subgraph", "escalation_subgraph", "__end__"]:
    """Evaluate intake subgraph outcome to dynamically route to dispatch, escalation, or END."""
    status = state.get("workflow_status")

    if status == "service_request_created":
        logger.info(
            "Dynamic Route: intake -> dispatch_subgraph (request_id=%s)",
            state.get("request_id"),
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="intake", to_route="dispatch").inc()
        return "dispatch_subgraph"

    if status == "escalated":
        logger.info(
            "Dynamic Route: intake -> escalation_subgraph (request_id=%s)",
            state.get("request_id"),
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="intake", to_route="escalation").inc()
        return "escalation_subgraph"

    logger.info(
        "Dynamic Route: intake halt (%s) -> END (request_id=%s)",
        status,
        state.get("request_id"),
    )
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="intake", to_route="end").inc()
    return END


def route_after_dispatch(
    state: FieldServiceState,
) -> Literal["build_appointment_proposal", "escalation_subgraph", "__end__"]:
    """Evaluate dispatch subgraph outcome: route to proposal, escalation, or END."""
    status = state.get("workflow_status")
    options = state.get("available_options", [])

    if status == "schedule_options_ready" and options:
        logger.info(
            "Dynamic Route: dispatch -> build_appointment_proposal (request_id=%s, options=%d)",
            state.get("request_id"),
            len(options),
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="dispatch", to_route="proposal").inc()
        return "build_appointment_proposal"

    if status in ("no_technician_available", "no_available_slots", "escalated"):
        logger.info(
            "Dynamic Route: dispatch -> escalation_subgraph (request_id=%s, status=%s)",
            state.get("request_id"),
            status,
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="dispatch", to_route="escalation").inc()
        return "escalation_subgraph"

    logger.info(
        "Dynamic Route: dispatch halt (%s) -> END (request_id=%s)",
        status,
        state.get("request_id"),
    )
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="dispatch", to_route="end").inc()
    return END


def route_after_human_review(
    state: FieldServiceState,
) -> Literal["appointment_subgraph", "handle_rejection", "__end__"]:
    """Evaluate human review decision: route to appointment creation or rejection."""
    status = state.get("approval_status")

    if status == "approved":
        logger.info(
            "Dynamic Route: human_review approved -> appointment_subgraph (request_id=%s)",
            state.get("request_id"),
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="human_review", to_route="appointment").inc()
        return "appointment_subgraph"

    if status == "rejected":
        logger.info(
            "Dynamic Route: human_review rejected -> handle_rejection (request_id=%s)",
            state.get("request_id"),
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="human_review", to_route="rejection").inc()
        return "handle_rejection"

    logger.warning(
        "Dynamic Route: unexpected approval status (%s) -> END (request_id=%s)",
        status,
        state.get("request_id"),
    )
    WORKFLOW_DEAD_ENDS_TOTAL.labels(stage="human_review").inc()
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="human_review", to_route="end").inc()
    return END


def route_after_appointment(
    state: FieldServiceState,
) -> Literal["__end__"]:
    """Evaluate appointment outcome: ends appointment finalization with valid state (created or needs_rescheduling)."""
    status = state.get("workflow_status")
    logger.info(
        "Dynamic Route: appointment outcome (%s) -> END (request_id=%s)",
        status,
        state.get("request_id"),
    )
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="appointment", to_route="end").inc()
    return END


def route_after_reschedule(
    state: FieldServiceState,
) -> Literal["dispatch_subgraph", "escalation_subgraph", "__end__"]:
    """Evaluate reschedule loop: if within bounds, redispatch; if exceeded, escalate."""
    status = state.get("workflow_status")

    if status == "ready_for_scheduling":
        logger.info(
            "Dynamic Route: reschedule redispatch -> dispatch_subgraph (request_id=%s)",
            state.get("request_id"),
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="reschedule", to_route="dispatch").inc()
        return "dispatch_subgraph"

    if status == "escalated":
        logger.info(
            "Dynamic Route: reschedule limit exceeded -> escalation_subgraph (request_id=%s)",
            state.get("request_id"),
        )
        WORKFLOW_ROUTES_TOTAL.labels(from_stage="reschedule", to_route="escalation").inc()
        return "escalation_subgraph"

    logger.info(
        "Dynamic Route: reschedule halt (%s) -> END (request_id=%s)",
        status,
        state.get("request_id"),
    )
    WORKFLOW_ROUTES_TOTAL.labels(from_stage="reschedule", to_route="end").inc()
    return END


# Backward-compatibility aliases for test suites
def route_after_validation(state: FieldServiceState) -> Literal["persist_service_request", "__end__"]:
    """Backward-compatible validation routing helper."""
    status = state.get("workflow_status")
    if status == "validated":
        return "persist_service_request"
    return END


def route_after_technician_matching(state: FieldServiceState) -> Literal["check_schedule", "__end__"]:
    """Backward-compatible matching routing helper."""
    status = state.get("workflow_status")
    if status == "ready_for_scheduling":
        return "check_schedule"
    return END


def _wrap_traced_node(node_name: str, node_func):
    def _traced_node_func(state: FieldServiceState):
        with trace_node(node_name, state):
            if hasattr(node_func, "invoke"):
                return node_func.invoke(state)
            return node_func(state)
    return _traced_node_func


# ==============================================================================
# 2. Main FieldOps Graph Builder
# ==============================================================================


def build_field_service_graph(
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Assemble the FieldOps LangGraph StateGraph with Subgraphs and Dynamic Routing."""
    workflow = StateGraph(FieldServiceState)

    # Compile Subgraphs
    intake_sg = build_intake_subgraph()
    dispatch_sg = build_dispatch_subgraph()
    appointment_sg = build_appointment_subgraph()
    reschedule_sg = build_reschedule_subgraph()
    escalation_sg = build_escalation_subgraph()

    # Add Subgraphs and HITL Nodes
    workflow.add_node("intake_subgraph", _wrap_traced_node("intake_subgraph", intake_sg))
    workflow.add_node("dispatch_subgraph", _wrap_traced_node("dispatch_subgraph", dispatch_sg))
    workflow.add_node("build_appointment_proposal", _wrap_traced_node("build_appointment_proposal", build_appointment_proposal_node))
    workflow.add_node("human_review", _wrap_traced_node("human_review", human_review_node))
    workflow.add_node("appointment_subgraph", _wrap_traced_node("appointment_subgraph", appointment_sg))
    workflow.add_node("reschedule_subgraph", _wrap_traced_node("reschedule_subgraph", reschedule_sg))
    workflow.add_node("escalation_subgraph", _wrap_traced_node("escalation_subgraph", escalation_sg))
    workflow.add_node("handle_rejection", _wrap_traced_node("handle_rejection", handle_rejection_node))

    # Connect Edges
    workflow.add_edge(START, "intake_subgraph")

    # Dynamic Route 1: Post-Intake
    workflow.add_conditional_edges(
        "intake_subgraph",
        route_after_intake,
        {
            "dispatch_subgraph": "dispatch_subgraph",
            "escalation_subgraph": "escalation_subgraph",
            END: END,
        },
    )

    # Dynamic Route 2: Post-Dispatch
    workflow.add_conditional_edges(
        "dispatch_subgraph",
        route_after_dispatch,
        {
            "build_appointment_proposal": "build_appointment_proposal",
            "escalation_subgraph": "escalation_subgraph",
            END: END,
        },
    )

    workflow.add_edge("build_appointment_proposal", "human_review")

    # Dynamic Route 3: Post-Human Review (Resume)
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "appointment_subgraph": "appointment_subgraph",
            "handle_rejection": "handle_rejection",
            END: END,
        },
    )

    # Route 4: Post-Appointment (Direct to END)
    workflow.add_edge("appointment_subgraph", END)

    # Dynamic Route 5: Post-Reschedule (Redispatch loop vs Escalation)
    workflow.add_conditional_edges(
        "reschedule_subgraph",
        route_after_reschedule,
        {
            "dispatch_subgraph": "dispatch_subgraph",
            "escalation_subgraph": "escalation_subgraph",
            END: END,
        },
    )

    workflow.add_edge("escalation_subgraph", END)
    workflow.add_edge("handle_rejection", END)

    effective_checkpointer = (
        checkpointer if checkpointer is not None else get_checkpointer()
    )
    return workflow.compile(checkpointer=effective_checkpointer)


field_service_graph = build_field_service_graph()
