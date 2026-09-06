"""Dispatch & Scheduling Decision Evaluator."""

from typing import Any

from fieldops.agent.decisions.decision_result import (
    DecisionAction,
    DecisionResult,
    HumanReviewLevel,
    ReasonCode,
)
from fieldops.agent.decisions.policies import EscalationPolicy


def evaluate_dispatch_decision(
    matching_status: str | None,
    candidate_technician_ids: list[int],
    scheduling_status: str | None,
    available_options: list[dict[str, Any]],
    urgency: str | None,
    sla_feasible: bool = True,
) -> DecisionResult:
    """Evaluate matching, scheduling, and SLA feasibility to determine dispatch routing."""
    # 1. No technician match in zone with skills
    if matching_status in ("no_candidates", "no_technician_available") or not candidate_technician_ids:
        esc = EscalationPolicy.evaluate(trigger_reason="no_candidates", urgency=urgency)
        return DecisionResult(
            action=DecisionAction.ESCALATE,
            reason_code=ReasonCode.NO_ELIGIBLE_TECHNICIAN,
            reason=esc["reason"],
            policy_version=esc["policy_version"],
            requires_human=True,
            required_role=esc["required_role"],
            retryable=False,
            metadata={"matching_status": matching_status, "urgency": urgency},
        )

    # 2. Time window requires clarification
    if scheduling_status == "needs_time_clarification":
        return DecisionResult(
            action=DecisionAction.ASK_FOR_INFORMATION,
            reason_code=ReasonCode.MISSING_TIME,
            reason="Customer preferred time window is unparseable or ambiguous. Specific time slot clarification required.",
            policy_version="1.0.0",
            requires_human=False,
            required_role=HumanReviewLevel.NONE,
            retryable=False,
            metadata={"scheduling_status": scheduling_status},
        )

    # 3. SLA feasibility violation
    if not sla_feasible:
        esc = EscalationPolicy.evaluate(trigger_reason="sla_impossible", urgency=urgency)
        return DecisionResult(
            action=DecisionAction.ESCALATE,
            reason_code=ReasonCode.SLA_CANNOT_BE_MET,
            reason=esc["reason"],
            policy_version=esc["policy_version"],
            requires_human=True,
            required_role=esc["required_role"],
            retryable=False,
            metadata={"sla_feasible": False, "urgency": urgency},
        )

    # 4. No schedule slots available
    if scheduling_status in ("no_available_slots", "no_slots") or not available_options:
        esc = EscalationPolicy.evaluate(trigger_reason="no_slots", urgency=urgency)
        return DecisionResult(
            action=DecisionAction.ESCALATE,
            reason_code=ReasonCode.NO_AVAILABLE_SLOTS,
            reason="Candidate technicians have no unreserved appointment slots during the requested window.",
            policy_version=esc["policy_version"],
            requires_human=True,
            required_role=esc["required_role"],
            retryable=False,
            metadata={"candidate_count": len(candidate_technician_ids)},
        )

    # 5. Proposal Ready
    return DecisionResult(
        action=DecisionAction.WAIT_FOR_APPROVAL,
        reason_code=ReasonCode.PROPOSAL_READY,
        reason=f"Candidate technicians matched ({len(candidate_technician_ids)}) and {len(available_options)} appointment options discovered. Awaiting operator review.",
        policy_version="1.0.0",
        requires_human=True,
        required_role=HumanReviewLevel.OPERATOR,
        retryable=False,
        metadata={"options_count": len(available_options)},
    )
