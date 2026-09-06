"""Formal Policy Definitions with Versioning (ApprovalPolicy, EscalationPolicy, RecoveryPolicy)."""

from datetime import datetime, timezone
import logging
from typing import Any

from fieldops.agent.decisions.decision_result import HumanReviewLevel, ReasonCode

logger = logging.getLogger(__name__)


class ApprovalPolicy:
    """Policy governing Human-In-The-Loop approval tiers, required roles, and override criteria."""

    POLICY_NAME = "ApprovalPolicy"
    POLICY_VERSION = "1.0.0"

    @classmethod
    def evaluate(
        cls,
        urgency: str | None = None,
        sla_deadline: datetime | str | None = None,
        is_sla_breached: bool = False,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        reschedule_count: int = 0,
        customer_tier: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate proposal and context against approval criteria.

        Returns:
            dict containing:
            - required_role: HumanReviewLevel
            - reason_code: str
            - reason: str
            - allowed_actions: list[str]
            - policy_version: str
        """
        urgency_norm = (urgency or "").lower()

        # 1. Emergency P0 Requests require elevated Senior Operator / Admin approval
        if urgency_norm == "emergency":
            return {
                "required_role": HumanReviewLevel.SENIOR_OPERATOR,
                "reason_code": ReasonCode.EMERGENCY_REQUIRES_ELEVATED_APPROVAL,
                "reason": "Emergency priority requires Senior Operator approval for immediate dispatch confirmation.",
                "allowed_actions": ["approve", "reject"],
                "policy_version": cls.POLICY_VERSION,
            }

        # 2. SLA Breached / Imminent Breach requires Senior Operator or Admin
        if is_sla_breached:
            return {
                "required_role": HumanReviewLevel.SENIOR_OPERATOR,
                "reason_code": ReasonCode.SLA_CANNOT_BE_MET,
                "reason": "SLA deadline is breached; elevated review required to authorize expedited dispatch.",
                "allowed_actions": ["approve", "reject"],
                "policy_version": cls.POLICY_VERSION,
            }

        # 3. Overtime Check (outside standard 08:00 - 18:00 or weekends)
        if start_time:
            dt_start = (
                datetime.fromisoformat(start_time)
                if isinstance(start_time, str)
                else start_time
            )
            # Weekend (Saturday=5, Sunday=6) or after 18:00 or before 08:00
            if dt_start.weekday() in (5, 6) or dt_start.hour < 8 or dt_start.hour >= 18:
                return {
                    "required_role": HumanReviewLevel.SENIOR_OPERATOR,
                    "reason_code": ReasonCode.OVERTIME_REQUIRES_APPROVAL,
                    "reason": f"Appointment scheduled at {dt_start.strftime('%Y-%m-%d %H:%M')} incurs overtime/off-hours and requires Senior Operator authorization.",
                    "allowed_actions": ["approve", "reject"],
                    "policy_version": cls.POLICY_VERSION,
                }

        # 4. Repeated Rescheduling (> 1 attempt) requires Senior Operator
        if reschedule_count >= 2:
            return {
                "required_role": HumanReviewLevel.SENIOR_OPERATOR,
                "reason_code": ReasonCode.RESCHEDULE_LIMIT_EXCEEDED,
                "reason": f"Request has been rescheduled {reschedule_count} times; elevated operator oversight required.",
                "allowed_actions": ["approve", "reject"],
                "policy_version": cls.POLICY_VERSION,
            }

        # 5. Standard Low / Medium / High Priority -> Standard Operator
        return {
            "required_role": HumanReviewLevel.OPERATOR,
            "reason_code": ReasonCode.PROPOSAL_READY,
            "reason": "Standard service appointment proposal within business hours requires Operator confirmation.",
            "allowed_actions": ["approve", "reject"],
            "policy_version": cls.POLICY_VERSION,
        }


class EscalationPolicy:
    """Policy governing routing of unresolvable or blocked requests to human intervention queues."""

    POLICY_NAME = "EscalationPolicy"
    POLICY_VERSION = "1.0.0"

    @classmethod
    def evaluate(
        cls,
        trigger_reason: str,
        urgency: str | None = None,
        reschedule_count: int = 0,
        clarification_count: int = 0,
    ) -> dict[str, Any]:
        """Classify escalation severity, required role, and notification priority.

        Returns:
            dict containing:
            - severity: str ("P0", "P1", "P2")
            - required_role: HumanReviewLevel
            - reason_code: str
            - reason: str
            - target_queue: str
            - policy_version: str
        """
        urgency_norm = (urgency or "").lower()

        if trigger_reason == "no_candidates" or trigger_reason == "no_technician":
            if urgency_norm == "emergency":
                severity = "P0"
                role = HumanReviewLevel.SENIOR_OPERATOR
                reason = "No eligible technician found for emergency request. Immediate dispatch intervention needed."
            else:
                severity = "P1"
                role = HumanReviewLevel.OPERATOR
                reason = "No technician possessing the required skills is available in the service zone."

            return {
                "severity": severity,
                "required_role": role,
                "reason_code": ReasonCode.NO_ELIGIBLE_TECHNICIAN,
                "reason": reason,
                "target_queue": "dispatch_escalations",
                "policy_version": cls.POLICY_VERSION,
            }

        if trigger_reason == "sla_impossible" or trigger_reason == "sla_breached":
            return {
                "severity": "P0" if urgency_norm == "emergency" else "P1",
                "required_role": HumanReviewLevel.SENIOR_OPERATOR,
                "reason_code": ReasonCode.SLA_CANNOT_BE_MET,
                "reason": "Candidate technicians cannot meet the required SLA deadline. Operator reassignment needed.",
                "target_queue": "sla_escalations",
                "policy_version": cls.POLICY_VERSION,
            }

        if trigger_reason == "clarification_limit":
            return {
                "severity": "P2",
                "required_role": HumanReviewLevel.OPERATOR,
                "reason_code": ReasonCode.CLARIFICATION_LIMIT_EXCEEDED,
                "reason": f"Clarification limit reached ({clarification_count} rounds). Routing to operator for manual outreach.",
                "target_queue": "customer_support",
                "policy_version": cls.POLICY_VERSION,
            }

        if trigger_reason == "reschedule_limit":
            return {
                "severity": "P1",
                "required_role": HumanReviewLevel.SENIOR_OPERATOR,
                "reason_code": ReasonCode.RESCHEDULE_LIMIT_EXCEEDED,
                "reason": f"Maximum automated reschedule attempts exceeded ({reschedule_count}). Requires manual dispatch coordination.",
                "target_queue": "dispatch_escalations",
                "policy_version": cls.POLICY_VERSION,
            }

        if trigger_reason == "integration_auth_failure":
            return {
                "severity": "P0",
                "required_role": HumanReviewLevel.ADMIN,
                "reason_code": ReasonCode.INTEGRATION_AUTH_FAILURE,
                "reason": "External calendar provider authentication expired or revoked. Admin intervention required.",
                "target_queue": "admin_system_alerts",
                "policy_version": cls.POLICY_VERSION,
            }

        return {
            "severity": "P2",
            "required_role": HumanReviewLevel.OPERATOR,
            "reason_code": ReasonCode.NO_AVAILABLE_SLOTS,
            "reason": f"Workflow escalation triggered by: {trigger_reason}",
            "target_queue": "general_escalations",
            "policy_version": cls.POLICY_VERSION,
        }


class RecoveryPolicy:
    """Policy classifying failures and directing automated retry vs async recovery vs human escalation."""

    POLICY_NAME = "RecoveryPolicy"
    POLICY_VERSION = "1.0.0"

    @classmethod
    def evaluate(
        cls,
        error_type: str,
        attempt_count: int = 1,
        retry_budget: int = 3,
        is_side_effect_safe: bool = True,
    ) -> dict[str, Any]:
        """Determine recovery action based on error classification.

        Returns:
            dict containing:
            - action: str ("retry", "async_recovery", "reschedule", "require_human", "stop")
            - retryable: bool
            - reason_code: str
            - reason: str
            - policy_version: str
        """
        # 1. Transient infrastructure / LLM errors
        if error_type in ("llm_timeout", "transient_network", "db_deadlock"):
            if attempt_count < retry_budget and is_side_effect_safe:
                return {
                    "action": "retry",
                    "retryable": True,
                    "reason_code": ReasonCode.TRANSIENT_INFRASTRUCTURE_FAILURE,
                    "reason": f"Transient failure ({error_type}). Safe to retry within budget (attempt {attempt_count}/{retry_budget}).",
                    "policy_version": cls.POLICY_VERSION,
                }
            else:
                return {
                    "action": "require_human",
                    "retryable": False,
                    "reason_code": ReasonCode.RETRY_BUDGET_EXHAUSTED,
                    "reason": f"Retry budget exhausted ({attempt_count}/{retry_budget}) for {error_type}. Escalating to human operator.",
                    "policy_version": cls.POLICY_VERSION,
                }

        # 2. Business appointment conflicts (deterministic business fact)
        if error_type in ("appointment_conflict", "slot_taken"):
            return {
                "action": "reschedule",
                "retryable": False,
                "reason_code": ReasonCode.APPOINTMENT_CONFLICT,
                "reason": "Proposed appointment slot is no longer available. Initiating automated redispatch/reschedule.",
                "policy_version": cls.POLICY_VERSION,
            }

        # 3. Auxiliary integration failure (e.g. Google Calendar transient error)
        if error_type in ("calendar_sync_transient", "notification_send_failed"):
            return {
                "action": "async_recovery",
                "retryable": True,
                "reason_code": ReasonCode.INTEGRATION_RECOVERY_REQUIRED,
                "reason": "Core business operation succeeded; auxiliary integration enqueued for asynchronous recovery.",
                "policy_version": cls.POLICY_VERSION,
            }

        # 4. External integration permanent auth error (401 / 403)
        if error_type in ("calendar_auth_failed", "external_credentials_invalid"):
            return {
                "action": "require_human",
                "retryable": False,
                "reason_code": ReasonCode.INTEGRATION_AUTH_FAILURE,
                "reason": "External integration credentials invalid. Requires administrator configuration.",
                "policy_version": cls.POLICY_VERSION,
            }

        # 5. Invariant / Validation fatal errors
        if error_type in ("workflow_invariant_error", "illegal_transition", "schema_invalid"):
            return {
                "action": "stop",
                "retryable": False,
                "reason_code": ReasonCode.WORKFLOW_INVARIANT_VIOLATION,
                "reason": f"Unrecoverable invariant or state integrity violation: {error_type}. Halting execution.",
                "policy_version": cls.POLICY_VERSION,
            }

        # Default fallback
        return {
            "action": "stop",
            "retryable": False,
            "reason_code": "UNKNOWN_ERROR",
            "reason": f"Unhandled error class: {error_type}",
            "policy_version": cls.POLICY_VERSION,
        }
