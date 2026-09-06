"""Workflow Decision Models and Enumerations for Phase 28."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionAction(str, Enum):
    """Permissible actions returned by decision evaluators."""

    CONTINUE = "continue"
    ASK_FOR_INFORMATION = "ask_for_information"
    DISPATCH = "dispatch"
    RESCHEDULE = "reschedule"
    ESCALATE = "escalate"
    WAIT_FOR_APPROVAL = "wait_for_approval"
    FINALIZE = "finalize"
    RETRY = "retry"
    REQUIRE_HUMAN = "require_human"
    STOP = "stop"


class HumanReviewLevel(str, Enum):
    """Hierarchical authorization levels for human review / HITL."""

    NONE = "none"
    OPERATOR = "operator"
    SENIOR_OPERATOR = "senior_operator"
    ADMIN = "admin"

    @classmethod
    def can_approve(cls, actor_role: str, required_level: "HumanReviewLevel") -> bool:
        """Evaluate if an actor's role satisfies the required review level."""
        hierarchy = {
            cls.NONE: 0,
            cls.OPERATOR: 1,
            cls.SENIOR_OPERATOR: 2,
            cls.ADMIN: 3,
        }
        role_map = {
            "operator": cls.OPERATOR,
            "senior_operator": cls.SENIOR_OPERATOR,
            "admin": cls.ADMIN,
        }
        actor_lvl = role_map.get(actor_role.lower(), cls.NONE)
        return hierarchy[actor_lvl] >= hierarchy[required_level]


# Standardized Reason Codes
class ReasonCode:
    """Standardized reason codes for decision attribution and audit trails."""

    VALID_REQUEST = "VALID_REQUEST"
    MISSING_LOCATION = "MISSING_LOCATION"
    MISSING_TIME = "MISSING_TIME"
    INVALID_SERVICE_TYPE = "INVALID_SERVICE_TYPE"
    INVALID_URGENCY = "INVALID_URGENCY"
    EMPTY_MESSAGE = "EMPTY_MESSAGE"
    NO_ELIGIBLE_TECHNICIAN = "NO_ELIGIBLE_TECHNICIAN"
    SLA_CANNOT_BE_MET = "SLA_CANNOT_BE_MET"
    NO_AVAILABLE_SLOTS = "NO_AVAILABLE_SLOTS"
    PROPOSAL_READY = "PROPOSAL_READY"
    APPROVED_BY_HUMAN = "APPROVED_BY_HUMAN"
    REJECTED_BY_HUMAN = "REJECTED_BY_HUMAN"
    OVERTIME_REQUIRES_APPROVAL = "OVERTIME_REQUIRES_APPROVAL"
    EMERGENCY_REQUIRES_ELEVATED_APPROVAL = "EMERGENCY_REQUIRES_ELEVATED_APPROVAL"
    APPOINTMENT_CONFLICT = "APPOINTMENT_CONFLICT"
    INTEGRATION_RECOVERY_REQUIRED = "INTEGRATION_RECOVERY_REQUIRED"
    INTEGRATION_AUTH_FAILURE = "INTEGRATION_AUTH_FAILURE"
    CLARIFICATION_LIMIT_EXCEEDED = "CLARIFICATION_LIMIT_EXCEEDED"
    RESCHEDULE_LIMIT_EXCEEDED = "RESCHEDULE_LIMIT_EXCEEDED"
    RETRY_BUDGET_EXHAUSTED = "RETRY_BUDGET_EXHAUSTED"
    ILLEGAL_TRANSITION = "ILLEGAL_TRANSITION"
    WORKFLOW_INVARIANT_VIOLATION = "WORKFLOW_INVARIANT_VIOLATION"
    TRANSIENT_INFRASTRUCTURE_FAILURE = "TRANSIENT_INFRASTRUCTURE_FAILURE"


@dataclass(frozen=True)
class DecisionResult:
    """Unified outcome structure returned by all business and operational decisions."""

    action: DecisionAction
    reason_code: str
    reason: str
    policy_version: str = "1.0.0"
    requires_human: bool = False
    required_role: HumanReviewLevel = HumanReviewLevel.NONE
    retryable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize into a clean dictionary suitable for LangGraph State and audit logging."""
        return {
            "action": self.action.value,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "requires_human": self.requires_human,
            "required_role": self.required_role.value,
            "retryable": self.retryable,
            "metadata": self.metadata,
        }
