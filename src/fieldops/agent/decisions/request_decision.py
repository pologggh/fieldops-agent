"""Request Intake & Validation Decision Node."""

from typing import Any

from fieldops.agent.decisions.decision_result import (
    DecisionAction,
    DecisionResult,
    HumanReviewLevel,
    ReasonCode,
)
from fieldops.agent.decisions.policies import EscalationPolicy

MAX_CLARIFICATION_ROUNDS = 3


def evaluate_request_intake_decision(
    workflow_status: str,
    validation_errors: list[str],
    service_type: str | None,
    urgency: str | None,
    location: str | None,
    clarification_count: int = 0,
) -> DecisionResult:
    """Determine the next routing action following request parsing and validation."""
    # 1. Check for fatal validation issues or missing critical information
    has_fatal_errors = workflow_status == "needs_information" or not service_type or not urgency

    if has_fatal_errors:
        # Check clarification loop limit to prevent infinite ping-pong
        if clarification_count >= MAX_CLARIFICATION_ROUNDS:
            esc = EscalationPolicy.evaluate(
                trigger_reason="clarification_limit",
                urgency=urgency,
                clarification_count=clarification_count,
            )
            return DecisionResult(
                action=DecisionAction.ESCALATE,
                reason_code=ReasonCode.CLARIFICATION_LIMIT_EXCEEDED,
                reason=esc["reason"],
                policy_version=esc["policy_version"],
                requires_human=True,
                required_role=esc["required_role"],
                retryable=False,
                metadata={"clarification_count": clarification_count, "errors": validation_errors},
            )

        # Determine primary missing field reason code
        reason_code = ReasonCode.INVALID_SERVICE_TYPE if not service_type else ReasonCode.INVALID_URGENCY
        return DecisionResult(
            action=DecisionAction.ASK_FOR_INFORMATION,
            reason_code=reason_code,
            reason=f"Customer request lacks critical fields: {', '.join(validation_errors) if validation_errors else 'missing required data'}. Clarification needed.",
            policy_version="1.0.0",
            requires_human=False,
            required_role=HumanReviewLevel.NONE,
            retryable=False,
            metadata={"clarification_count": clarification_count, "errors": validation_errors},
        )

    # 2. Valid service_type & urgency: Proceed to dispatch (missing location is evaluated in technician matching)
    reason_code = ReasonCode.MISSING_LOCATION if not location or not str(location).strip() else ReasonCode.VALID_REQUEST
    reason = (
        "Request valid but missing location. Proceeding to persistence and zone matching resolution."
        if reason_code == ReasonCode.MISSING_LOCATION
        else "Request fields are structurally complete and business-valid. Ready for technician matching."
    )
    return DecisionResult(
        action=DecisionAction.DISPATCH,
        reason_code=reason_code,
        reason=reason,
        policy_version="1.0.0",
        requires_human=False,
        required_role=HumanReviewLevel.NONE,
        retryable=False,
        metadata={"service_type": service_type, "urgency": urgency, "location": location},
    )
