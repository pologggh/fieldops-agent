import logging
import time
from typing import Literal
import uuid

from langgraph.types import Command

from fieldops.agent.state import FieldServiceState, create_initial_state
from fieldops.core.exceptions import ConflictError, ResourceNotFoundError
from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    WORKFLOW_ACTIVE_DURATION_SECONDS,
    WORKFLOW_DURATION_SECONDS,
    WORKFLOW_STEP_COUNT,
    WORKFLOWS_TOTAL,
)

logger = logging.getLogger(__name__)



class WorkflowNotFoundError(ResourceNotFoundError):
    """Raised when an operation is attempted on a non-existent workflow thread."""

    pass


class WorkflowAlreadyCompletedError(ConflictError):
    """Raised when attempting to approve or resume a workflow that is not waiting for approval."""

    pass


def run_field_service_workflow(
    message: str,
    customer_name: str = "",
    email: str = "",
    phone: str | None = None,
    request_id: str | None = None,
    source: str | None = None,
    inbound_event_id: int | None = None,
    graph=None,
) -> FieldServiceState:
    """Execute the FieldOps service request intake, validation, persistence, and proposal workflow.

    Coordinates initial state creation, graph invocation, and state return.
    If the workflow interrupts at the human_review stage, returns the state
    paused in 'waiting_for_approval'.

    Args:
        message: Raw customer request text.
        customer_name: Customer full name.
        email: Customer contact email.
        phone: Optional customer phone number.
        request_id: Optional tracking identifier. If None, generates a new uuid4.
        source: Optional channel source (e.g. 'web', 'fake_email', 'webhook').
        inbound_event_id: Optional primary key from inbound_events table.
        graph: Optional compiled LangGraph instance (defaults to field_service_graph).

    Returns:
        FieldServiceState dictionary after passing through the LangGraph pipeline.
    """
    from fieldops.agent.graph import field_service_graph

    active_graph = graph or field_service_graph
    actual_request_id = request_id or str(uuid.uuid4())
    logger.info(
        "Application workflow initiated: request_id=%s, email=%s, source=%s, inbound_event_id=%s",
        actual_request_id,
        email,
        source,
        inbound_event_id,
    )

    initial_state = create_initial_state(
        request_id=actual_request_id,
        raw_message=message,
        customer_name=customer_name,
        customer_email=email,
        customer_phone=phone,
        source=source,
        inbound_event_id=inbound_event_id,
    )

    start_time = time.perf_counter()
    emit_event(
        "workflow.started",
        request_id=actual_request_id,
        email=email,
        source=source,
    )

    config = {"configurable": {"thread_id": actual_request_id}}
    raw_result = active_graph.invoke(initial_state, config=config)

    # Read state values from snapshot
    state_snapshot = active_graph.get_state(config)
    final_state = (
        state_snapshot.values
        if state_snapshot and state_snapshot.values
        else raw_result
    )
    cleaned_state = {k: v for k, v in final_state.items() if k != "__interrupt__"}
    duration_s = time.perf_counter() - start_time
    duration_ms = round(duration_s * 1000, 2)
    result_status = cleaned_state.get("workflow_status") or "unknown"

    WORKFLOWS_TOTAL.labels(result=result_status).inc()
    WORKFLOW_DURATION_SECONDS.labels(result=result_status).observe(duration_s)
    WORKFLOW_ACTIVE_DURATION_SECONDS.observe(duration_s)
    WORKFLOW_STEP_COUNT.observe(cleaned_state.get("step_count", 1))

    emit_event(
        "workflow.completed",
        request_id=actual_request_id,
        workflow_status=result_status,
        duration_ms=duration_ms,
        customer_id=cleaned_state.get("customer_id"),
        service_request_id=cleaned_state.get("service_request_id"),
    )

    logger.info(
        "Application workflow step completed: request_id=%s, workflow_status=%s, customer_id=%s, service_request_id=%s",
        actual_request_id,
        result_status,
        cleaned_state.get("customer_id"),
        cleaned_state.get("service_request_id"),
    )

    return cleaned_state  # type: ignore[return-value]



def resume_field_service_workflow(
    request_id: str,
    decision: Literal["approve", "reject"],
    reason: str | None = None,
    actor_role: str = "operator",
    graph=None,
) -> FieldServiceState:
    """Resume an interrupted FieldOps workflow with an operator approval or rejection decision.

    Args:
        request_id: Identifier of the workflow thread to resume.
        decision: Operator decision ('approve' or 'reject').
        reason: Optional explanatory reason.
        actor_role: Caller internal role ('operator', 'senior_operator', 'admin').
        graph: Optional compiled LangGraph instance (defaults to field_service_graph).

    Returns:
        Updated FieldServiceState after resuming and completing the workflow.

    Raises:
        WorkflowNotFoundError: If no checkpoint exists for the given request_id.
        WorkflowAlreadyCompletedError: If the workflow is not paused in 'waiting_for_approval'.
    """
    from fieldops.agent.graph import field_service_graph

    active_graph = graph or field_service_graph
    config = {"configurable": {"thread_id": request_id}}
    state_snapshot = active_graph.get_state(config)

    if (
        not state_snapshot
        or not state_snapshot.values
        or not state_snapshot.values.get("request_id")
    ):
        logger.warning(
            "Attempted to resume non-existent workflow thread: request_id=%s",
            request_id,
        )
        raise WorkflowNotFoundError(
            f"Workflow with request_id '{request_id}' not found."
        )

    current_workflow_status = state_snapshot.values.get("workflow_status")
    approval_status = state_snapshot.values.get("approval_status")

    if (
        current_workflow_status != "waiting_for_approval"
        or approval_status in ("approved", "rejected")
        or not state_snapshot.next
    ):
        logger.warning(
            "Attempted to resume already completed/invalid workflow: request_id=%s, status=%s, approval=%s",
            request_id,
            current_workflow_status,
            approval_status,
        )
        raise WorkflowAlreadyCompletedError(
            f"Workflow '{request_id}' is not awaiting approval (current status: '{current_workflow_status}', approval_status: '{approval_status}')."
        )

    # Validate permission hierarchy before resuming execution to protect thread state
    required_role_str = state_snapshot.values.get("human_review_level", "operator")
    from fieldops.agent.decisions.decision_result import HumanReviewLevel
    required_role = (
        HumanReviewLevel(required_role_str)
        if required_role_str in HumanReviewLevel._value2member_map_
        else HumanReviewLevel.OPERATOR
    )
    if not HumanReviewLevel.can_approve(actor_role, required_role):
        from fieldops.core.exceptions import WorkflowStateError
        raise WorkflowStateError(
            f"User with role '{actor_role}' cannot approve proposal requiring '{required_role.value}'. Elevated approval required."
        )

    logger.info(
        "Resuming workflow thread: request_id=%s, decision=%s, reason=%s, actor_role=%s",
        request_id,
        decision,
        reason,
        actor_role,
    )

    start_time = time.perf_counter()
    emit_event(
        "approval.received",
        request_id=request_id,
        decision=decision,
        reason=reason,
        actor_role=actor_role,
    )

    raw_result = active_graph.invoke(
        Command(
            resume={
                "decision": decision,
                "reason": reason,
                "actor_role": actor_role,
            }
        ),
        config=config,
    )

    resumed_snapshot = active_graph.get_state(config)
    final_state = (
        resumed_snapshot.values
        if resumed_snapshot and resumed_snapshot.values
        else raw_result
    )
    cleaned_state = {k: v for k, v in final_state.items() if k != "__interrupt__"}
    duration_s = time.perf_counter() - start_time
    duration_ms = round(duration_s * 1000, 2)
    final_status = cleaned_state.get("workflow_status") or "unknown"

    WORKFLOWS_TOTAL.labels(result=final_status).inc()
    WORKFLOW_DURATION_SECONDS.labels(result=final_status).observe(duration_s)
    WORKFLOW_ACTIVE_DURATION_SECONDS.observe(duration_s)
    WORKFLOW_STEP_COUNT.observe(cleaned_state.get("step_count", 1))

    emit_event(
        "workflow.completed",
        request_id=request_id,
        workflow_status=final_status,
        approval_status=cleaned_state.get("approval_status"),
        duration_ms=duration_ms,
        appointment_id=cleaned_state.get("appointment_id"),
        service_request_id=cleaned_state.get("service_request_id"),
    )

    logger.info(
        "Workflow resumption completed: request_id=%s, workflow_status=%s, approval_status=%s",
        request_id,
        final_status,
        cleaned_state.get("approval_status"),
    )

    return cleaned_state  # type: ignore[return-value]

