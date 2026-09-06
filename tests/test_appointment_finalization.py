from datetime import datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.application.appointment_service import AppointmentService
from fieldops.application.field_service_workflow import (
    resume_field_service_workflow,
    run_field_service_workflow,
)
from fieldops.core.config import settings
from fieldops.db.models import Appointment, AuditLog, Customer, ServiceRequest
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.service_request_repository import (
    ServiceRequestRepository,
)
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)
TZ = ZoneInfo(settings.BUSINESS_TIMEZONE)


# ==============================================================================
# Unit & Service Tests: AppointmentService Atomic Transactions
# ==============================================================================


def test_appointment_service_create_success(test_db_session: Session) -> None:
    """1. Approve with no conflict -> Appointment created, ServiceRequest scheduled, AuditLog created."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    sr_repo = ServiceRequestRepository(test_db_session)
    sr = sr_repo.create(
        customer_id=1,
        raw_message="AC broken",
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        status="pending",
    )

    today = datetime(2026, 9, 6, tzinfo=TZ).date()
    start_dt = datetime.combine(today, time(13, 0), tzinfo=TZ)
    end_dt = datetime.combine(today, time(15, 0), tzinfo=TZ)

    service = AppointmentService(test_db_session)
    result = service.finalize_appointment(
        service_request_id=sr.id,
        technician_id=1,
        start_time=start_dt,
        end_time=end_dt,
    )

    assert result.success is True
    assert result.appointment_id is not None
    assert result.appointment_status == "scheduled"
    assert result.conflict_detected is False
    assert result.finalization_status == "completed"

    # Verify Appointment persisted
    appt = test_db_session.get(Appointment, result.appointment_id)
    assert appt is not None
    assert appt.technician_id == 1
    assert appt.service_request_id == sr.id
    assert appt.status == "scheduled"

    # Verify ServiceRequest status updated
    reloaded_sr = test_db_session.get(ServiceRequest, sr.id)
    assert reloaded_sr.status == "scheduled"

    # Verify AuditLog recorded
    audit_repo = AuditLogRepository(test_db_session)
    logs = audit_repo.list_by_entity("appointment", result.appointment_id)
    assert len(logs) == 1
    assert logs[0].action == "appointment.created"
    assert logs[0].details["technician_id"] == 1


def test_appointment_service_rejection(test_db_session: Session) -> None:
    """2. Operator rejects proposal -> ServiceRequest marked rejected, AuditLog recorded, no Appointment."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    sr_repo = ServiceRequestRepository(test_db_session)
    sr = sr_repo.create(
        customer_id=1,
        raw_message="AC broken",
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        status="pending",
    )

    service = AppointmentService(test_db_session)
    rejection_res = service.handle_rejection(
        service_request_id=sr.id,
        reason="Customer cannot accommodate time",
    )

    assert rejection_res.finalization_status == "rejected"

    # Verify ServiceRequest status is rejected
    reloaded_sr = test_db_session.get(ServiceRequest, sr.id)
    assert reloaded_sr.status == "rejected"

    # Verify no Appointment created
    appts = list(
        test_db_session.scalars(
            select(Appointment).where(Appointment.service_request_id == sr.id)
        ).all()
    )
    assert len(appts) == 0

    # Verify AuditLog
    audit_repo = AuditLogRepository(test_db_session)
    logs = audit_repo.list_by_entity("service_request", sr.id)
    assert len(logs) == 1
    assert logs[0].action == "appointment.rejected"
    assert logs[0].details["reason"] == "Customer cannot accommodate time"


def test_appointment_service_conflict_recheck_aborts_creation(
    test_db_session: Session,
) -> None:
    """3. Final conflict re-check detects overlap -> aborts appointment creation, updates status to needs_rescheduling."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    today = datetime(2026, 9, 6, tzinfo=TZ).date()
    slot_start = datetime.combine(today, time(13, 0), tzinfo=TZ)
    slot_end = datetime.combine(today, time(15, 0), tzinfo=TZ)

    sr_repo = ServiceRequestRepository(test_db_session)
    sr1 = sr_repo.create(1, "Prior job", "HVAC", "medium", "Shinjuku")
    sr2 = sr_repo.create(1, "New job", "HVAC", "high", "Shinjuku")

    # Manually insert prior appointment occupying 14:00 - 16:00
    appt_repo = AppointmentRepository(test_db_session)
    prior_appt = appt_repo.create(
        service_request_id=sr1.id,
        technician_id=1,
        start_time=datetime.combine(today, time(14, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(16, 0), tzinfo=TZ),
        status="scheduled",
    )

    service = AppointmentService(test_db_session)
    result = service.finalize_appointment(
        service_request_id=sr2.id,
        technician_id=1,
        start_time=slot_start,
        end_time=slot_end,
    )

    assert result.success is False
    assert result.appointment_id is None
    assert result.conflict_detected is True
    assert result.finalization_status == "conflict"

    # Verify no appointment for sr2
    sr2_appts = list(
        test_db_session.scalars(
            select(Appointment).where(Appointment.service_request_id == sr2.id)
        ).all()
    )
    assert len(sr2_appts) == 0

    # Verify ServiceRequest.status is updated to needs_rescheduling
    reloaded_sr2 = test_db_session.get(ServiceRequest, sr2.id)
    assert reloaded_sr2.status == "needs_rescheduling"

    # Verify conflict audit log
    audit_repo = AuditLogRepository(test_db_session)
    logs = audit_repo.list_by_entity("service_request", sr2.id)
    assert len(logs) == 1
    assert logs[0].action == "appointment.conflict"
    assert prior_appt.id in logs[0].details["conflicting_appointment_ids"]


def test_transaction_rollback_atomicity_on_failure(test_db_session: Session) -> None:
    """4. If writing audit log fails during finalization, entire transaction rolls back."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    sr_repo = ServiceRequestRepository(test_db_session)
    sr = sr_repo.create(1, "Job", "HVAC", "high", "Shinjuku", status="pending")

    today = datetime(2026, 9, 6, tzinfo=TZ).date()
    start_dt = datetime.combine(today, time(10, 0), tzinfo=TZ)
    end_dt = datetime.combine(today, time(12, 0), tzinfo=TZ)

    service = AppointmentService(test_db_session)

    # Force audit_log_repo.create to raise an exception
    with patch.object(
        service.audit_log_repo,
        "create",
        side_effect=RuntimeError("Audit database connection lost"),
    ):
        with pytest.raises(RuntimeError, match="Audit database connection lost"):
            service.finalize_appointment(
                service_request_id=sr.id,
                technician_id=1,
                start_time=start_dt,
                end_time=end_dt,
            )

    # Verify atomic rollback: no Appointment created, ServiceRequest status remains 'pending'
    reloaded_sr = test_db_session.get(ServiceRequest, sr.id)
    assert reloaded_sr.status == "pending"

    appts = list(
        test_db_session.scalars(
            select(Appointment).where(Appointment.service_request_id == sr.id)
        ).all()
    )
    assert len(appts) == 0


def test_idempotency_duplicate_finalize(test_db_session: Session) -> None:
    """5. Duplicate finalize call on same service_request_id returns existing appointment without creating duplicates."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    sr_repo = ServiceRequestRepository(test_db_session)
    sr = sr_repo.create(1, "Job", "HVAC", "high", "Shinjuku", status="pending")

    today = datetime(2026, 9, 6, tzinfo=TZ).date()
    start_dt = datetime.combine(today, time(13, 0), tzinfo=TZ)
    end_dt = datetime.combine(today, time(15, 0), tzinfo=TZ)

    service = AppointmentService(test_db_session)
    res1 = service.finalize_appointment(sr.id, 1, start_dt, end_dt)
    assert res1.success is True

    # Call finalize again
    res2 = service.finalize_appointment(sr.id, 1, start_dt, end_dt)
    assert res2.success is True
    assert res2.appointment_id == res1.appointment_id

    # Verify only 1 appointment exists in database
    appts = list(
        test_db_session.scalars(
            select(Appointment).where(Appointment.service_request_id == sr.id)
        ).all()
    )
    assert len(appts) == 1


def test_adjacent_boundary_slots_allowed(test_db_session: Session) -> None:
    """6. Adjacent back-to-back appointment (13:00-15:00 and 15:00-17:00) is allowed."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    today = datetime(2026, 9, 6, tzinfo=TZ).date()
    t13 = datetime.combine(today, time(13, 0), tzinfo=TZ)
    t15 = datetime.combine(today, time(15, 0), tzinfo=TZ)
    t17 = datetime.combine(today, time(17, 0), tzinfo=TZ)

    sr_repo = ServiceRequestRepository(test_db_session)
    sr1 = sr_repo.create(1, "Job 1", "HVAC", "high", "Shinjuku")
    sr2 = sr_repo.create(1, "Job 2", "HVAC", "high", "Shinjuku")

    service = AppointmentService(test_db_session)
    res1 = service.finalize_appointment(sr1.id, 1, t13, t15)
    assert res1.success is True

    # 15:00 - 17:00 immediately follows 13:00 - 15:00
    res2 = service.finalize_appointment(sr2.id, 1, t15, t17)
    assert res2.success is True
    assert res2.appointment_id is not None


def test_cancelled_appointment_does_not_block(test_db_session: Session) -> None:
    """7. Cancelled appointment in the exact same slot does not block new appointment."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    today = datetime(2026, 9, 6, tzinfo=TZ).date()
    t13 = datetime.combine(today, time(13, 0), tzinfo=TZ)
    t15 = datetime.combine(today, time(15, 0), tzinfo=TZ)

    sr_repo = ServiceRequestRepository(test_db_session)
    sr1 = sr_repo.create(1, "Old Job", "HVAC", "medium", "Shinjuku")
    sr2 = sr_repo.create(1, "New Job", "HVAC", "high", "Shinjuku")

    appt_repo = AppointmentRepository(test_db_session)
    appt_repo.create(sr1.id, 1, t13, t15, status="cancelled")

    service = AppointmentService(test_db_session)
    res = service.finalize_appointment(sr2.id, 1, t13, t15)
    assert res.success is True
    assert res.appointment_id is not None


# ==============================================================================
# Workflow & API Integration Tests
# ==============================================================================


def test_full_workflow_approval_creates_appointment(test_db_session: Session) -> None:
    """8. Full workflow: intake -> parse -> propose -> interrupt -> resume(approve) -> finalize -> appointment_created."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC unit not cooling",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        paused_state = run_field_service_workflow(
            message="Need AC repair in Shinjuku tomorrow afternoon",
            customer_name="Alice",
            email="alice@example.com",
            request_id="wf-final-1",
        )

    assert paused_state["workflow_status"] == "waiting_for_approval"
    sr_id = paused_state["service_request_id"]
    assert sr_id is not None

    # Resume with approval
    final_state = resume_field_service_workflow(
        request_id="wf-final-1",
        decision="approve",
    )

    assert final_state["workflow_status"] == "appointment_created"
    assert final_state["approval_status"] == "approved"
    assert final_state["appointment_id"] is not None
    assert final_state["appointment_status"] == "scheduled"
    assert final_state["conflict_detected"] is False

    # Check database persistence
    appt = test_db_session.get(Appointment, final_state["appointment_id"])
    assert appt is not None
    assert appt.service_request_id == sr_id
    assert appt.status == "scheduled"

    sr = test_db_session.get(ServiceRequest, sr_id)
    assert sr.status == "scheduled"


def test_api_approval_conflict_response(test_db_session: Session) -> None:
    """9. Approval API handles conflict gracefully: returns 200 with needs_rescheduling and conflict_detected=True."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC unit not cooling",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        create_resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "090-1111-2222",
                "message": "Need AC repair in Shinjuku tomorrow afternoon",
            },
        )

    assert create_resp.status_code == 201
    create_data = create_resp.json()
    req_id = create_data["request_id"]
    proposal = create_data["appointment_proposal"]
    assert proposal is not None

    # Simulate another booking taking the exact proposed slot before operator approves
    p_start = datetime.fromisoformat(proposal["start_time"])
    p_end = datetime.fromisoformat(proposal["end_time"])

    appt_repo = AppointmentRepository(test_db_session)
    sr_repo = ServiceRequestRepository(test_db_session)
    other_sr = sr_repo.create(1, "Other request", "HVAC", "high", "Shinjuku")
    appt_repo.create(
        service_request_id=other_sr.id,
        technician_id=proposal["technician_id"],
        start_time=p_start,
        end_time=p_end,
        status="scheduled",
    )
    test_db_session.commit()

    # Now operator approves
    approval_resp = client.post(
        f"/service-requests/{req_id}/approval",
        json={"decision": "approve"},
    )

    assert approval_resp.status_code == 200
    approval_data = approval_resp.json()
    assert approval_data["workflow_status"] == "needs_rescheduling"
    assert approval_data["conflict_detected"] is True
    assert approval_data["appointment_id"] is None
