from datetime import datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from fieldops.application.field_service_workflow import (
    run_field_service_workflow,
)
from fieldops.core.config import settings
from fieldops.db.models import Appointment, Customer, ServiceRequest, Technician
from fieldops.domain.services.scheduling import (
    SchedulingService,
    generate_candidate_slots,
    has_time_conflict,
)
from fieldops.domain.services.time_window_parser import (
    TimeWindow,
    TimeWindowParser,
)
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.repositories.appointment_repository import AppointmentRepository
from scripts.seed import seed_customers, seed_technicians

TZ = ZoneInfo(settings.BUSINESS_TIMEZONE)


# ==============================================================================
# Unit Tests: Time Conflict Logic (Section 22)
# ==============================================================================


def test_has_time_conflict_non_overlapping() -> None:
    """1. Completely separate intervals: 09:00-11:00 vs 13:00-15:00 -> no conflict."""
    today = datetime(2026, 9, 5, tzinfo=TZ).date()
    slot_start = datetime.combine(today, time(9, 0), tzinfo=TZ)
    slot_end = datetime.combine(today, time(11, 0), tzinfo=TZ)
    appt_start = datetime.combine(today, time(13, 0), tzinfo=TZ)
    appt_end = datetime.combine(today, time(15, 0), tzinfo=TZ)

    assert not has_time_conflict(slot_start, slot_end, appt_start, appt_end)
    assert not has_time_conflict(appt_start, appt_end, slot_start, slot_end)


def test_has_time_conflict_exact_match() -> None:
    """2. Completely identical intervals: 13:00-15:00 vs 13:00-15:00 -> conflict."""
    today = datetime(2026, 9, 5, tzinfo=TZ).date()
    t1 = datetime.combine(today, time(13, 0), tzinfo=TZ)
    t2 = datetime.combine(today, time(15, 0), tzinfo=TZ)

    assert has_time_conflict(t1, t2, t1, t2)


def test_has_time_conflict_partial_overlap() -> None:
    """3. Partial overlap: 14:00-16:00 vs 15:00-17:00 -> conflict."""
    today = datetime(2026, 9, 5, tzinfo=TZ).date()
    slot_start = datetime.combine(today, time(14, 0), tzinfo=TZ)
    slot_end = datetime.combine(today, time(16, 0), tzinfo=TZ)
    appt_start = datetime.combine(today, time(15, 0), tzinfo=TZ)
    appt_end = datetime.combine(today, time(17, 0), tzinfo=TZ)

    assert has_time_conflict(slot_start, slot_end, appt_start, appt_end)
    assert has_time_conflict(appt_start, appt_end, slot_start, slot_end)


def test_has_time_conflict_enclosure() -> None:
    """4. One interval strictly contains the other: 13:00-17:00 vs 14:00-15:00 -> conflict."""
    today = datetime(2026, 9, 5, tzinfo=TZ).date()
    outer_start = datetime.combine(today, time(13, 0), tzinfo=TZ)
    outer_end = datetime.combine(today, time(17, 0), tzinfo=TZ)
    inner_start = datetime.combine(today, time(14, 0), tzinfo=TZ)
    inner_end = datetime.combine(today, time(15, 0), tzinfo=TZ)

    assert has_time_conflict(outer_start, outer_end, inner_start, inner_end)
    assert has_time_conflict(inner_start, inner_end, outer_start, outer_end)


def test_has_time_conflict_adjacent_boundary() -> None:
    """5. Adjacent boundary: 13:00-15:00 vs 15:00-17:00 -> no conflict."""
    today = datetime(2026, 9, 5, tzinfo=TZ).date()
    slot1_start = datetime.combine(today, time(13, 0), tzinfo=TZ)
    slot1_end = datetime.combine(today, time(15, 0), tzinfo=TZ)
    slot2_start = datetime.combine(today, time(15, 0), tzinfo=TZ)
    slot2_end = datetime.combine(today, time(17, 0), tzinfo=TZ)

    assert not has_time_conflict(slot1_start, slot1_end, slot2_start, slot2_end)
    assert not has_time_conflict(slot2_start, slot2_end, slot1_start, slot1_end)


# ==============================================================================
# Unit Tests: TimeWindowParser & Slot Generation
# ==============================================================================


def test_time_window_parser_supported_relative_phrases() -> None:
    """8. Parse supported relative phrases into correct operating hours."""
    parser = TimeWindowParser()
    ref_time = datetime(2026, 9, 5, 10, 0, tzinfo=TZ)

    # Today afternoon
    w_today_afternoon = parser.parse("this afternoon", reference_time=ref_time)
    assert w_today_afternoon is not None
    assert w_today_afternoon.start_time == datetime(2026, 9, 5, 13, 0, tzinfo=TZ)
    assert w_today_afternoon.end_time == datetime(2026, 9, 5, 17, 0, tzinfo=TZ)

    # Tomorrow morning
    w_tmrw_morning = parser.parse("tomorrow morning", reference_time=ref_time)
    assert w_tmrw_morning is not None
    assert w_tmrw_morning.start_time == datetime(2026, 9, 6, 9, 0, tzinfo=TZ)
    assert w_tmrw_morning.end_time == datetime(2026, 9, 6, 12, 0, tzinfo=TZ)

    # Tomorrow afternoon
    w_tmrw_afternoon = parser.parse("tomorrow afternoon", reference_time=ref_time)
    assert w_tmrw_afternoon is not None
    assert w_tmrw_afternoon.start_time == datetime(2026, 9, 6, 13, 0, tzinfo=TZ)
    assert w_tmrw_afternoon.end_time == datetime(2026, 9, 6, 17, 0, tzinfo=TZ)


def test_time_window_parser_unsupported_expressions() -> None:
    """9. Unsupported or ambiguous natural language returns None."""
    parser = TimeWindowParser()
    assert parser.parse("Friday after 3pm") is None
    assert parser.parse("next week sometime") is None
    assert parser.parse("") is None
    assert parser.parse(None) is None


def test_generate_candidate_slots() -> None:
    """8. Slot generation: 13:00 - 17:00, 120 min duration, 60 min step -> 3 slots."""
    today = datetime(2026, 9, 5, tzinfo=TZ).date()
    window = TimeWindow(
        start_time=datetime.combine(today, time(13, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(17, 0), tzinfo=TZ),
    )

    slots = generate_candidate_slots(window, duration_minutes=120, step_minutes=60)
    assert len(slots) == 3
    assert slots[0] == TimeWindow(
        start_time=datetime.combine(today, time(13, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(15, 0), tzinfo=TZ),
    )
    assert slots[1] == TimeWindow(
        start_time=datetime.combine(today, time(14, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(16, 0), tzinfo=TZ),
    )
    assert slots[2] == TimeWindow(
        start_time=datetime.combine(today, time(15, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(17, 0), tzinfo=TZ),
    )


# ==============================================================================
# Repository Integration: Blocking Statuses (Section 22: 6 & 7)
# ==============================================================================


def test_appointment_repository_blocking_statuses(test_db_session: Session) -> None:
    """6 & 7. Only scheduled/confirmed/in_progress block; cancelled/rejected do not block."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    repo = AppointmentRepository(test_db_session)
    today = datetime(2026, 9, 5, tzinfo=TZ).date()
    t1 = datetime.combine(today, time(13, 0), tzinfo=TZ)
    t2 = datetime.combine(today, time(15, 0), tzinfo=TZ)

    ken = test_db_session.query(Technician).filter_by(name="Ken Tanaka").one()
    sr = ServiceRequest(
        customer_id=1,
        raw_message="test",
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        status="created",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    # Scheduled appointment -> blocks
    appt_scheduled = repo.create(sr.id, ken.id, t1, t2, status="scheduled")
    blocking_scheduled = repo.get_blocking_by_technician_and_window(
        ken.id, t1 - timedelta(hours=1), t2 + timedelta(hours=1)
    )
    assert len(blocking_scheduled) == 1

    # Cancelled appointment -> does not block
    appt_scheduled.status = "cancelled"
    test_db_session.flush()
    blocking_cancelled = repo.get_blocking_by_technician_and_window(
        ken.id, t1 - timedelta(hours=1), t2 + timedelta(hours=1)
    )
    assert len(blocking_cancelled) == 0


# ==============================================================================
# Domain Service Integration (Section 23)
# ==============================================================================


def test_scheduling_service_filters_conflicted_slots(test_db_session: Session) -> None:
    """Ken is occupied 13:00-15:00; Yuki is free. Only non-conflicting slots are returned."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    ken = test_db_session.query(Technician).filter_by(name="Ken Tanaka").one()
    yuki = test_db_session.query(Technician).filter_by(name="Yuki Sato").one()

    today = (datetime.now(TZ) + timedelta(days=1)).date()
    sr = ServiceRequest(
        customer_id=1,
        raw_message="test",
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        status="created",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    appt_repo = AppointmentRepository(test_db_session)
    # Ken is booked 13:00-15:00
    appt_repo.create(
        service_request_id=sr.id,
        technician_id=ken.id,
        start_time=datetime.combine(today, time(13, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(15, 0), tzinfo=TZ),
        status="scheduled",
    )

    sched_service = SchedulingService(appt_repo)
    window = TimeWindow(
        start_time=datetime.combine(today, time(13, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(17, 0), tzinfo=TZ),
    )

    result = sched_service.check_availability(
        candidate_technician_ids=[ken.id, yuki.id],
        window=window,
    )

    assert result.scheduling_status == "schedule_options_ready"
    options = result.available_options

    # Ken should ONLY have slot 15:00-17:00 available (13:00-15:00 and 14:00-16:00 conflict)
    ken_options = [opt for opt in options if opt["technician_id"] == ken.id]
    assert len(ken_options) == 1
    assert datetime.fromisoformat(ken_options[0]["start_time"]) == datetime.combine(today, time(15, 0), tzinfo=TZ)

    # Yuki was free: has all 3 slots (13:00-15:00, 14:00-16:00, 15:00-17:00)
    yuki_options = [opt for opt in options if opt["technician_id"] == yuki.id]
    assert len(yuki_options) == 3


# ==============================================================================
# Full LangGraph Workflow End-to-End Tests (Section 24)
# ==============================================================================


def test_full_workflow_scheduling_success(test_db_session: Session) -> None:
    """Full workflow: parse -> validate -> persist -> match -> check_schedule -> schedule_options_ready."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC unit stopped working in Shinjuku",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="My AC stopped working in Shinjuku, need someone tomorrow afternoon.",
            customer_name="Alice",
            email="alice@example.com",
            phone="090-1111-2222",
        )

    assert final_state["workflow_status"] in ("waiting_for_approval", "schedule_options_ready")
    assert final_state["scheduling_status"] == "schedule_options_ready"
    assert final_state["matching_status"] == "matched"
    assert len(final_state["available_options"]) > 0
    assert final_state["requested_window_start"] is not None
    assert final_state["requested_window_end"] is not None


def test_full_workflow_unsupported_preferred_time_needs_clarification(
    test_db_session: Session,
) -> None:
    """Unsupported preferred_time -> halts at needs_time_clarification."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="medium",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="sometime next month when possible",
        problem_description="AC tune up",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="AC tune up next month in Shinjuku",
            customer_name="Alice",
            email="alice@example.com",
            phone="123456",
        )

    assert final_state["workflow_status"] == "needs_time_clarification"
    assert final_state["scheduling_status"] == "needs_time_clarification"
    assert final_state["available_options"] == []


def test_full_workflow_all_slots_conflict_results_in_no_available_slots(
    test_db_session: Session,
) -> None:
    """When technician is fully booked across the entire window -> no_available_slots."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    ken = test_db_session.query(Technician).filter_by(name="Ken Tanaka").one()
    today = (datetime.now(TZ) + timedelta(days=1)).date()

    # Pre-book Ken for the entire afternoon (13:00 - 17:00)
    sr = ServiceRequest(
        customer_id=1,
        raw_message="All day overhaul",
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        status="created",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    appt_repo = AppointmentRepository(test_db_session)
    appt_repo.create(
        service_request_id=sr.id,
        technician_id=ken.id,
        start_time=datetime.combine(today, time(13, 0), tzinfo=TZ),
        end_time=datetime.combine(today, time(17, 0), tzinfo=TZ),
        status="scheduled",
    )

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC stopped working",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="AC stopped working in Shinjuku tomorrow afternoon",
            customer_name="Bob",
            email="bob@example.com",
            phone="090-3333-4444",
        )

    assert final_state["workflow_status"] == "no_available_slots"
    assert final_state["scheduling_status"] == "no_available_slots"
    assert final_state["available_options"] == []


def test_api_service_request_with_scheduling_options(
    test_db_session: Session,
) -> None:
    """Test POST /service-requests API returns available_options and requested window."""
    from fastapi.testclient import TestClient
    from fieldops.main import app
    from tests.conftest import TEST_OPERATOR_HEADERS

    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="tomorrow afternoon",
        problem_description="AC stopped working with burning smell",
    )

    client = TestClient(app, headers=TEST_OPERATOR_HEADERS)
    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        response = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "090-1111-2222",
                "message": "My AC stopped working in Shinjuku, need someone tomorrow afternoon.",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["workflow_status"] in ("waiting_for_approval", "schedule_options_ready")
    assert data["scheduling_status"] == "schedule_options_ready"
    assert data["requested_window_start"] is not None
    assert data["requested_window_end"] is not None
    assert len(data["available_options"]) > 0
    assert data["appointment_proposal"] is not None
    first_opt = data["available_options"][0]
    assert "technician_id" in first_opt
    assert "start_time" in first_opt
    assert "end_time" in first_opt

