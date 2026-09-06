"""Unit tests for Phase 28 Workflow Decision Layer and Policies."""

from datetime import datetime, timezone
import pytest

from fieldops.agent.decisions.approval_decision import (
    evaluate_proposal_approval_level,
    evaluate_resume_approval_decision,
)
from fieldops.agent.decisions.compensation import (
    CompensationAction,
    CompensationEngine,
)
from fieldops.agent.decisions.decision_result import (
    DecisionAction,
    HumanReviewLevel,
    ReasonCode,
)
from fieldops.agent.decisions.dispatch_decision import evaluate_dispatch_decision
from fieldops.agent.decisions.policies import (
    ApprovalPolicy,
    EscalationPolicy,
    RecoveryPolicy,
)
from fieldops.agent.decisions.recovery_decision import evaluate_recovery_decision
from fieldops.agent.decisions.request_decision import evaluate_request_intake_decision


def test_request_decision_valid():
    """Valid complete input routes to DISPATCH with VALID_REQUEST."""
    res = evaluate_request_intake_decision(
        workflow_status="validated",
        validation_errors=[],
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
    )
    assert res.action == DecisionAction.DISPATCH
    assert res.reason_code == ReasonCode.VALID_REQUEST
    assert not res.requires_human


def test_request_decision_missing_required_field():
    """Missing service_type routes to ASK_FOR_INFORMATION."""
    res = evaluate_request_intake_decision(
        workflow_status="needs_information",
        validation_errors=["service_type is missing."],
        service_type=None,
        urgency="medium",
        location="Shinjuku",
        clarification_count=1,
    )
    assert res.action == DecisionAction.ASK_FOR_INFORMATION
    assert res.reason_code == ReasonCode.INVALID_SERVICE_TYPE


def test_request_decision_clarification_limit():
    """Exceeding clarification limit (3 rounds) escalates to operator assistance."""
    res = evaluate_request_intake_decision(
        workflow_status="needs_information",
        validation_errors=["service_type is missing."],
        service_type=None,
        urgency="medium",
        location="Shinjuku",
        clarification_count=3,
    )
    assert res.action == DecisionAction.ESCALATE
    assert res.reason_code == ReasonCode.CLARIFICATION_LIMIT_EXCEEDED
    assert res.requires_human is True
    assert res.required_role == HumanReviewLevel.OPERATOR


def test_dispatch_decision_success():
    """Matched candidates and available slots route to WAIT_FOR_APPROVAL."""
    res = evaluate_dispatch_decision(
        matching_status="matched",
        candidate_technician_ids=[1, 2],
        scheduling_status="schedule_options_ready",
        available_options=[{"technician_id": 1, "start_time": "2026-09-07T10:00:00+09:00"}],
        urgency="medium",
    )
    assert res.action == DecisionAction.WAIT_FOR_APPROVAL
    assert res.reason_code == ReasonCode.PROPOSAL_READY


def test_dispatch_decision_no_technician():
    """No eligible technician escalates to dispatch operations."""
    res = evaluate_dispatch_decision(
        matching_status="no_candidates",
        candidate_technician_ids=[],
        scheduling_status=None,
        available_options=[],
        urgency="high",
    )
    assert res.action == DecisionAction.ESCALATE
    assert res.reason_code == ReasonCode.NO_ELIGIBLE_TECHNICIAN
    assert res.requires_human is True


def test_dispatch_decision_sla_breach():
    """SLA impossibility triggers SLA escalation to Senior Operator."""
    res = evaluate_dispatch_decision(
        matching_status="matched",
        candidate_technician_ids=[1],
        scheduling_status="schedule_options_ready",
        available_options=[{"technician_id": 1}],
        urgency="emergency",
        sla_feasible=False,
    )
    assert res.action == DecisionAction.ESCALATE
    assert res.reason_code == ReasonCode.SLA_CANNOT_BE_MET
    assert res.required_role == HumanReviewLevel.SENIOR_OPERATOR


def test_approval_policy_standard_vs_emergency():
    """Normal requests require OPERATOR; emergency requires SENIOR_OPERATOR."""
    normal = ApprovalPolicy.evaluate(urgency="medium")
    assert normal["required_role"] == HumanReviewLevel.OPERATOR

    emergency = ApprovalPolicy.evaluate(urgency="emergency")
    assert emergency["required_role"] == HumanReviewLevel.SENIOR_OPERATOR
    assert emergency["reason_code"] == ReasonCode.EMERGENCY_REQUIRES_ELEVATED_APPROVAL


def test_approval_policy_overtime():
    """Appointments scheduled off-hours require SENIOR_OPERATOR."""
    overtime = ApprovalPolicy.evaluate(
        urgency="low",
        start_time="2026-09-07T19:30:00+09:00",  # 19:30 is off-hours (>18:00)
    )
    assert overtime["required_role"] == HumanReviewLevel.SENIOR_OPERATOR
    assert overtime["reason_code"] == ReasonCode.OVERTIME_REQUIRES_APPROVAL


def test_resume_role_hierarchy_authorization():
    """Operator cannot approve proposal requiring Senior Operator; Admin can approve all."""
    # Operator attempting senior operator review -> denied
    denied = evaluate_resume_approval_decision(
        decision="approve",
        reason="Looks ok",
        actor_role="operator",
        required_role=HumanReviewLevel.SENIOR_OPERATOR,
    )
    assert denied.reason_code == "INSUFFICIENT_ROLE_PRIVILEGES"

    # Senior operator approving senior operator review -> approved
    approved = evaluate_resume_approval_decision(
        decision="approve",
        reason="Approved by lead",
        actor_role="senior_operator",
        required_role=HumanReviewLevel.SENIOR_OPERATOR,
    )
    assert approved.action == DecisionAction.FINALIZE
    assert approved.reason_code == ReasonCode.APPROVED_BY_HUMAN

    # Admin approving senior operator review -> approved
    admin_approved = evaluate_resume_approval_decision(
        decision="approve",
        reason="Admin override",
        actor_role="admin",
        required_role=HumanReviewLevel.SENIOR_OPERATOR,
    )
    assert admin_approved.action == DecisionAction.FINALIZE


def test_recovery_policy_classification():
    """Verify recovery policy classifies transient vs auth vs conflict errors."""
    # Transient timeout within budget -> retry
    t = evaluate_recovery_decision("llm_timeout", attempt_count=1, retry_budget=3)
    assert t.action == DecisionAction.RETRY
    assert t.retryable is True

    # Transient timeout budget exhausted -> require human
    exhausted = evaluate_recovery_decision("llm_timeout", attempt_count=3, retry_budget=3)
    assert exhausted.action == DecisionAction.REQUIRE_HUMAN
    assert exhausted.reason_code == ReasonCode.RETRY_BUDGET_EXHAUSTED

    # Conflict -> reschedule
    conf = evaluate_recovery_decision("appointment_conflict")
    assert conf.action == DecisionAction.RESCHEDULE

    # Calendar auth failed -> require admin
    auth_err = evaluate_recovery_decision("calendar_auth_failed")
    assert auth_err.action == DecisionAction.REQUIRE_HUMAN
    assert auth_err.required_role == HumanReviewLevel.ADMIN


def test_compensation_engine_core_success():
    """Calendar failure after committed appointment flags async recovery without rolling back appointment."""
    res = CompensationEngine.evaluate_calendar_sync_failure(
        appointment_id=99,
        provider_error="HTTP 503 Service Unavailable",
        is_permanent_auth_error=False,
    )
    assert res.required is True
    assert res.action == CompensationAction.ASYNC_CALENDAR_RETRY
    assert res.status == "pending_async"
    assert res.reason_code == ReasonCode.INTEGRATION_RECOVERY_REQUIRED
