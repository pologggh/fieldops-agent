import logging
from typing import Any

from fieldops.agent.decisions.approval_decision import (
    evaluate_proposal_approval_level,
)
from fieldops.agent.invariants import (
    validate_workflow_invariants,
    validate_workflow_transition,
)
from fieldops.agent.state import FieldServiceState
from fieldops.core.logging import emit_event
from fieldops.db.session import SessionLocal
from fieldops.domain.services.appointment_proposal import (
    AppointmentProposalService,
)
from fieldops.observability.metrics import (
    WORKFLOW_DECISIONS_TOTAL,
    WORKFLOW_HUMAN_REVIEWS_TOTAL,
)
from fieldops.repositories.technician_repository import TechnicianRepository

logger = logging.getLogger(__name__)


def build_appointment_proposal_node(state: FieldServiceState) -> dict[str, Any]:
    """Node generating a recommended appointment proposal and determining approval tier.

    Reads:
        state["available_options"]
        state["service_request_id"]
        state["candidate_technician_ids"]
        state["urgency"]
        state["reschedule_count"]

    Returns:
        appointment_proposal: dict[str, Any] | None
        workflow_status: str
        approval_status: str
        human_review_required: bool
        human_review_level: str
        last_decision: dict[str, Any]
    """
    request_id = state.get("request_id")
    step_count = state.get("step_count", 0) + 1
    current_status = state.get("workflow_status", "schedule_options_ready")
    logger.info("Node [build_appointment_proposal] started: request_id=%s", request_id)

    available_options = state.get("available_options", [])
    service_request_id = state.get("service_request_id")
    candidate_ids = state.get("candidate_technician_ids", [])

    if not available_options:
        logger.warning(
            "No available options to build proposal for request_id=%s", request_id
        )
        validate_workflow_transition(current_status, "no_available_slots")
        return {
            "step_count": step_count,
            "appointment_proposal": None,
            "workflow_status": "no_available_slots",
            "approval_status": None,
            "human_review_required": False,
            "human_review_level": "none",
        }

    # Fetch technician display names for operator review readability
    technician_names: dict[int, str] = {}
    try:
        with SessionLocal() as session:
            tech_repo = TechnicianRepository(session)
            for tid in candidate_ids:
                tech = tech_repo.get_by_id(tid)
                if tech:
                    technician_names[tech.id] = tech.name
    except Exception as e:
        logger.warning("Could not fetch technician display names: %s", e)

    proposal = AppointmentProposalService.select_proposal(
        available_options=available_options,
        service_request_id=service_request_id,
        technician_names=technician_names,
    )

    validate_workflow_transition(current_status, "waiting_for_approval")

    # Evaluate Tiered Approval Policy
    policy_decision = evaluate_proposal_approval_level(
        urgency=state.get("urgency"),
        start_time=proposal.get("start_time") if proposal else None,
        end_time=proposal.get("end_time") if proposal else None,
        reschedule_count=state.get("reschedule_count", 0),
    )

    WORKFLOW_DECISIONS_TOTAL.labels(
        decision_type="approval_policy_eval", action=policy_decision.action.value
    ).inc()

    WORKFLOW_HUMAN_REVIEWS_TOTAL.labels(
        review_level=policy_decision.required_role.value,
        review_type="appointment_proposal",
    ).inc()

    emit_event(
        "workflow.human_review_required",
        request_id=request_id,
        service_request_id=service_request_id,
        required_role=policy_decision.required_role.value,
        reason_code=policy_decision.reason_code,
        policy_version=policy_decision.policy_version,
    )

    history = list(state.get("decision_history", []))
    history.append(policy_decision.to_dict())

    logger.info(
        "Node [build_appointment_proposal] completed: request_id=%s, proposed_tech=%s, required_role=%s",
        request_id,
        proposal.get("technician_id") if proposal else None,
        policy_decision.required_role.value,
    )

    return {
        "step_count": step_count,
        "appointment_proposal": proposal,
        "workflow_status": "waiting_for_approval",
        "approval_status": "pending",
        "human_review_required": True,
        "human_review_level": policy_decision.required_role.value,
        "last_decision": policy_decision.to_dict(),
        "decision_history": history,
    }
