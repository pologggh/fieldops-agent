"""Approval Subgraph Decision & Tiered HITL Verification."""

from datetime import datetime
from typing import Any

from fieldops.agent.decisions.decision_result import (
    DecisionAction,
    DecisionResult,
    HumanReviewLevel,
    ReasonCode,
)
from fieldops.agent.decisions.policies import ApprovalPolicy


def evaluate_proposal_approval_level(
    urgency: str | None,
    sla_deadline: datetime | str | None = None,
    is_sla_breached: bool = False,
    start_time: datetime | str | None = None,
    end_time: datetime | str | None = None,
    reschedule_count: int = 0,
) -> DecisionResult:
    """Evaluate proposal criteria prior to LangGraph interrupt to determine required reviewer role."""
    policy_res = ApprovalPolicy.evaluate(
        urgency=urgency,
        sla_deadline=sla_deadline,
        is_sla_breached=is_sla_breached,
        start_time=start_time,
        end_time=end_time,
        reschedule_count=reschedule_count,
    )

    return DecisionResult(
        action=DecisionAction.WAIT_FOR_APPROVAL,
        reason_code=policy_res["reason_code"],
        reason=policy_res["reason"],
        policy_version=policy_res["policy_version"],
        requires_human=True,
        required_role=policy_res["required_role"],
        retryable=False,
        metadata={
            "allowed_actions": policy_res["allowed_actions"],
            "urgency": urgency,
            "reschedule_count": reschedule_count,
        },
    )


def evaluate_resume_approval_decision(
    decision: str,
    reason: str | None,
    actor_role: str,
    required_role: HumanReviewLevel,
) -> DecisionResult:
    """Validate operator resume decision and enforce role hierarchy authorization."""
    # Enforce role hierarchy on resumption
    if not HumanReviewLevel.can_approve(actor_role, required_role):
        return DecisionResult(
            action=DecisionAction.REQUIRE_HUMAN,
            reason_code="INSUFFICIENT_ROLE_PRIVILEGES",
            reason=f"User with role '{actor_role}' cannot approve proposal requiring '{required_role.value}'. Elevated approval required.",
            policy_version=ApprovalPolicy.POLICY_VERSION,
            requires_human=True,
            required_role=required_role,
            retryable=False,
            metadata={"actor_role": actor_role, "required_role": required_role.value},
        )

    decision_norm = decision.strip().lower()

    if decision_norm == "approve":
        return DecisionResult(
            action=DecisionAction.FINALIZE,
            reason_code=ReasonCode.APPROVED_BY_HUMAN,
            reason=f"Proposal approved by {actor_role} ({reason or 'Standard authorization'}). Proceeding to appointment finalization.",
            policy_version=ApprovalPolicy.POLICY_VERSION,
            requires_human=False,
            required_role=HumanReviewLevel.NONE,
            retryable=False,
            metadata={"decision": "approve", "actor_role": actor_role},
        )

    return DecisionResult(
        action=DecisionAction.STOP,
        reason_code=ReasonCode.REJECTED_BY_HUMAN,
        reason=f"Proposal rejected by {actor_role}: {reason or 'No reason provided'}.",
        policy_version=ApprovalPolicy.POLICY_VERSION,
        requires_human=False,
        required_role=HumanReviewLevel.NONE,
        retryable=False,
        metadata={"decision": "reject", "actor_role": actor_role},
    )
