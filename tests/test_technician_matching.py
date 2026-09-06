from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from fieldops.application.field_service_workflow import (
    run_field_service_workflow,
)
from fieldops.db.models import Technician, TechnicianSkill
from fieldops.domain.services.technician_matching import (
    TechnicianMatchingService,
)
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.repositories.technician_repository import TechnicianRepository
from scripts.seed import seed_technicians


def _create_technician(
    session: Session,
    name: str,
    service_area: str,
    status: str,
    skills: list[str],
) -> Technician:
    tech = Technician(name=name, service_area=service_area, status=status)
    session.add(tech)
    session.flush()
    for s in skills:
        session.add(TechnicianSkill(technician_id=tech.id, skill=s))
    session.flush()
    return tech


# ==============================================================================
# Domain Unit Tests (Section 17)
# ==============================================================================


def test_matching_rule_active_correct_area_and_skill(test_db_session: Session) -> None:
    """1. active + correct area + skill -> match."""
    tech = _create_technician(
        test_db_session, "Ken", "Shinjuku", "active", ["HVAC"]
    )
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result = service.match_technicians("Shinjuku", ["HVAC"])
    assert result.matching_status == "matched"
    assert tech.id in result.candidate_technician_ids


def test_matching_rule_inactive_technician_excluded(test_db_session: Session) -> None:
    """2. inactive technician -> does not match."""
    tech = _create_technician(
        test_db_session, "InactiveKen", "Shinjuku", "inactive", ["HVAC"]
    )
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result = service.match_technicians("Shinjuku", ["HVAC"])
    assert result.matching_status == "no_candidates"
    assert tech.id not in result.candidate_technician_ids


def test_matching_rule_wrong_service_area_excluded(test_db_session: Session) -> None:
    """3. wrong service area -> does not match."""
    _create_technician(test_db_session, "Haru", "Yokohama", "active", ["HVAC"])
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result = service.match_technicians("Shinjuku", ["HVAC"])
    assert result.matching_status == "no_candidates"
    assert result.candidate_technician_ids == []


def test_matching_rule_wrong_skill_excluded(test_db_session: Session) -> None:
    """4. wrong skill -> does not match."""
    _create_technician(
        test_db_session, "Yuki", "Shinjuku", "active", ["Plumbing"]
    )
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result = service.match_technicians("Shinjuku", ["HVAC"])
    assert result.matching_status == "no_candidates"
    assert result.candidate_technician_ids == []


def test_matching_rule_multiple_skills_superset_matches(
    test_db_session: Session,
) -> None:
    """5. Technician has multiple skills and contains required skill -> match."""
    tech = _create_technician(
        test_db_session, "Haru", "Yokohama", "active", ["HVAC", "Electrical"]
    )
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result = service.match_technicians("Yokohama", ["HVAC"])
    assert result.matching_status == "matched"
    assert tech.id in result.candidate_technician_ids


def test_matching_rule_not_all_required_skills_satisfied(
    test_db_session: Session,
) -> None:
    """6. Technician skills do not satisfy all required skills -> does not match."""
    _create_technician(test_db_session, "Ken", "Shinjuku", "active", ["HVAC"])
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    # Requested skills require both HVAC and Electrical, but Ken only has HVAC
    result = service.match_technicians("Shinjuku", ["HVAC", "Electrical"])
    assert result.matching_status == "no_candidates"
    assert result.candidate_technician_ids == []


def test_matching_rule_missing_location(test_db_session: Session) -> None:
    """7. location is None or whitespace -> needs_location."""
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result_none = service.match_technicians(None, ["HVAC"])
    assert result_none.matching_status == "needs_location"
    assert result_none.candidate_technician_ids == []

    result_blank = service.match_technicians("   ", ["HVAC"])
    assert result_blank.matching_status == "needs_location"
    assert result_blank.candidate_technician_ids == []


def test_matching_rule_empty_required_skills(test_db_session: Session) -> None:
    """8. required_skills is empty -> needs_skill_information."""
    _create_technician(test_db_session, "Ken", "Shinjuku", "active", ["HVAC"])
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result_empty = service.match_technicians("Shinjuku", [])
    assert result_empty.matching_status == "needs_skill_information"
    assert result_empty.candidate_technician_ids == []

    result_none = service.match_technicians("Shinjuku", None)
    assert result_none.matching_status == "needs_skill_information"
    assert result_none.candidate_technician_ids == []


def test_matching_rule_no_candidates(test_db_session: Session) -> None:
    """9. no matching technicians found -> no_candidates."""
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result = service.match_technicians("Chiba", ["HVAC"])
    assert result.matching_status == "no_candidates"
    assert result.candidate_technician_ids == []


def test_matching_rule_multiple_qualifying_technicians(
    test_db_session: Session,
) -> None:
    """10. Multiple qualifying technicians -> returns all candidate IDs without ranking."""
    tech1 = _create_technician(
        test_db_session, "Ken", "Shinjuku", "active", ["HVAC"]
    )
    tech2 = _create_technician(
        test_db_session, "Ren", "Shinjuku", "active", ["HVAC", "Plumbing"]
    )
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    result = service.match_technicians("Shinjuku", ["HVAC"])
    assert result.matching_status == "matched"
    assert sorted(result.candidate_technician_ids) == sorted([tech1.id, tech2.id])


# ==============================================================================
# Seed Integration Tests (Section 18)
# ==============================================================================


def test_seed_data_integration_queries(test_db_session: Session) -> None:
    """Verify matching against official seed data:

    - Shinjuku + HVAC -> Ken Tanaka
    - Shinjuku + Plumbing -> Yuki Sato
    - Yokohama + HVAC -> Haru Suzuki
    - Shinjuku + Electrical -> no_candidates
    """
    seed_technicians(test_db_session)
    repo = TechnicianRepository(test_db_session)
    service = TechnicianMatchingService(repo)

    # 1. Shinjuku + HVAC -> Ken Tanaka
    res1 = service.match_technicians("Shinjuku", ["HVAC"])
    assert res1.matching_status == "matched"
    assert len(res1.candidate_technician_ids) == 1
    tech1 = repo.get_by_id(res1.candidate_technician_ids[0])
    assert tech1 is not None and tech1.name == "Ken Tanaka"

    # 2. Shinjuku + Plumbing -> Yuki Sato
    res2 = service.match_technicians("Shinjuku", ["Plumbing"])
    assert res2.matching_status == "matched"
    assert len(res2.candidate_technician_ids) == 1
    tech2 = repo.get_by_id(res2.candidate_technician_ids[0])
    assert tech2 is not None and tech2.name == "Yuki Sato"

    # 3. Yokohama + HVAC -> Haru Suzuki
    res3 = service.match_technicians("Yokohama", ["HVAC"])
    assert res3.matching_status == "matched"
    assert len(res3.candidate_technician_ids) == 1
    tech3 = repo.get_by_id(res3.candidate_technician_ids[0])
    assert tech3 is not None and tech3.name == "Haru Suzuki"

    # 4. Shinjuku + Electrical -> no_candidates in seed
    res4 = service.match_technicians("Shinjuku", ["Electrical"])
    assert res4.matching_status == "no_candidates"
    assert res4.candidate_technician_ids == []


# ==============================================================================
# Workflow End-to-End Tests (Section 19)
# ==============================================================================


def test_workflow_matches_ken_tanaka_for_shinjuku_hvac(
    test_db_session: Session,
) -> None:
    """Full workflow test: parses request, persists service request, and matches Ken Tanaka."""
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="this afternoon",
        problem_description="AC stopped working and smells like burning",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="My AC stopped working in Shinjuku.",
            customer_name="Alice",
            email="alice@example.com",
            phone="123456",
        )

    # Workflow advances through matching, schedule check, and pauses at approval
    assert final_state["workflow_status"] in (
        "ready_for_scheduling",
        "schedule_options_ready",
        "waiting_for_approval",
    )
    assert final_state["matching_status"] == "matched"
    assert len(final_state["candidate_technician_ids"]) == 1

    repo = TechnicianRepository(test_db_session)
    matched_tech = repo.get_by_id(final_state["candidate_technician_ids"][0])
    assert matched_tech is not None
    assert matched_tech.name == "Ken Tanaka"


def test_workflow_no_technician_available_status(
    test_db_session: Session,
) -> None:
    """Workflow sets no_technician_available status when no technician matches skills in area."""
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="Electrical",
        urgency="medium",
        location="Shinjuku",
        required_skills=["Electrical"],  # In Shinjuku, no seed tech has Electrical
        preferred_time=None,
        problem_description="Light fixture sparking",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="Light fixture sparking in Shinjuku",
            customer_name="Alice",
            email="alice@example.com",
            phone="123456",
        )

    assert final_state["workflow_status"] == "no_technician_available"
    assert final_state["matching_status"] == "no_candidates"
    assert final_state["candidate_technician_ids"] == []


def test_workflow_needs_location_status(test_db_session: Session) -> None:
    """Workflow sets needs_location status when location was not provided."""
    seed_technicians(test_db_session)

    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="low",
        location=None,  # Missing location
        required_skills=["HVAC"],
        preferred_time=None,
        problem_description="AC fan is noisy",
    )

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=mock_parsed,
    ):
        final_state = run_field_service_workflow(
            message="AC fan is noisy somewhere",
            customer_name="Bob",
            email="bob@example.com",
            phone=None,
        )

    assert final_state["workflow_status"] == "needs_location"
    assert final_state["matching_status"] == "needs_location"
    assert final_state["candidate_technician_ids"] == []
