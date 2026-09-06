"""Compensation Semantics and Core Business Fact Guarantees for Phase 28."""

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any

from fieldops.agent.decisions.decision_result import ReasonCode

logger = logging.getLogger(__name__)


class CompensationAction(str, Enum):
    """Actions performed during multi-step distributed compensation."""

    NONE = "none"
    ASYNC_CALENDAR_RETRY = "async_calendar_retry"
    CANCEL_OLD_CALENDAR_EVENT = "cancel_old_calendar_event"
    RETRY_NOTIFICATION = "retry_notification"
    ROLLBACK_TRANSACTION = "rollback_transaction"
    FLAG_OPERATOR_INTERVENTION = "flag_operator_intervention"


@dataclass(frozen=True)
class CompensationResult:
    """Formal record of compensation evaluation or action."""

    required: bool
    action: CompensationAction
    status: str  # "completed", "pending_async", "failed", "unnecessary"
    reason_code: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "action": self.action.value,
            "status": self.status,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "details": self.details,
        }


class CompensationEngine:
    """Evaluates whether compensation is required and ensures Core Business Facts are preserved.

    Architectural Principle:
    A committed Appointment is an authoritative Business Fact.
    Third-party external failures (e.g., Google Calendar timeout, Email SMTP error)
    MUST NOT invalidate or delete the committed appointment.
    Instead, compensation queues an asynchronous recovery job.
    """

    @classmethod
    def evaluate_calendar_sync_failure(
        cls,
        appointment_id: int,
        provider_error: str,
        is_permanent_auth_error: bool = False,
    ) -> CompensationResult:
        """Handle calendar failure after appointment database commit."""
        if is_permanent_auth_error:
            logger.error(
                "Permanent authentication failure for Calendar sync on Appointment %s: %s",
                appointment_id,
                provider_error,
            )
            return CompensationResult(
                required=True,
                action=CompensationAction.FLAG_OPERATOR_INTERVENTION,
                status="pending_operator",
                reason_code=ReasonCode.INTEGRATION_AUTH_FAILURE,
                reason="Calendar credentials invalid. Appointment remains valid, but administrator intervention required to restore sync.",
                details={"appointment_id": appointment_id, "error": provider_error},
            )

        logger.warning(
            "Transient calendar failure for Appointment %s. Flagging for async recovery: %s",
            appointment_id,
            provider_error,
        )
        return CompensationResult(
            required=True,
            action=CompensationAction.ASYNC_CALENDAR_RETRY,
            status="pending_async",
            reason_code=ReasonCode.INTEGRATION_RECOVERY_REQUIRED,
            reason="Core appointment committed successfully. Auxiliary calendar sync scheduled for asynchronous retry.",
            details={"appointment_id": appointment_id, "error": provider_error},
        )

    @classmethod
    def evaluate_reschedule_compensation(
        cls,
        old_appointment_id: int,
        new_appointment_id: int,
        old_calendar_event_id: str | None = None,
    ) -> CompensationResult:
        """Handle compensation when rescheduling replaces an existing appointment."""
        if old_calendar_event_id:
            return CompensationResult(
                required=True,
                action=CompensationAction.CANCEL_OLD_CALENDAR_EVENT,
                status="pending_async",
                reason_code="RESCHEDULE_CALENDAR_CLEANUP",
                reason="New appointment booked; old calendar event enqueued for asynchronous cancellation.",
                details={
                    "old_appointment_id": old_appointment_id,
                    "new_appointment_id": new_appointment_id,
                    "calendar_event_id": old_calendar_event_id,
                },
            )

        return CompensationResult(
            required=False,
            action=CompensationAction.NONE,
            status="unnecessary",
            reason_code="NO_CALENDAR_CLEANUP_NEEDED",
            reason="No existing external calendar event requires cancellation.",
            details={"old_appointment_id": old_appointment_id, "new_appointment_id": new_appointment_id},
        )
