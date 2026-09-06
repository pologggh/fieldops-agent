"""Workflow Recovery & Error Classification Decision Engine."""

from typing import Any

from fieldops.agent.decisions.decision_result import (
    DecisionAction,
    DecisionResult,
    HumanReviewLevel,
    ReasonCode,
)
from fieldops.agent.decisions.policies import RecoveryPolicy


def evaluate_recovery_decision(
    error_type: str,
    error_message: str | None = None,
    attempt_count: int = 1,
    retry_budget: int = 3,
    is_side_effect_safe: bool = True,
) -> DecisionResult:
    """Classify runtime failure and determine appropriate recovery strategy."""
    policy_res = RecoveryPolicy.evaluate(
        error_type=error_type,
        attempt_count=attempt_count,
        retry_budget=retry_budget,
        is_side_effect_safe=is_side_effect_safe,
    )

    action_map = {
        "retry": DecisionAction.RETRY,
        "async_recovery": DecisionAction.CONTINUE,
        "reschedule": DecisionAction.RESCHEDULE,
        "require_human": DecisionAction.REQUIRE_HUMAN,
        "stop": DecisionAction.STOP,
    }
    action = action_map.get(policy_res["action"], DecisionAction.STOP)

    requires_human = action == DecisionAction.REQUIRE_HUMAN
    required_role = (
        HumanReviewLevel.ADMIN
        if policy_res["reason_code"] == ReasonCode.INTEGRATION_AUTH_FAILURE
        else (HumanReviewLevel.OPERATOR if requires_human else HumanReviewLevel.NONE)
    )

    return DecisionResult(
        action=action,
        reason_code=policy_res["reason_code"],
        reason=policy_res["reason"],
        policy_version=policy_res["policy_version"],
        requires_human=requires_human,
        required_role=required_role,
        retryable=policy_res["retryable"],
        metadata={
            "error_type": error_type,
            "error_message": error_message,
            "attempt_count": attempt_count,
            "retry_budget": retry_budget,
        },
    )
