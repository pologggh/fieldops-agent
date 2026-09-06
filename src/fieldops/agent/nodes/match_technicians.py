import logging
from typing import Any

from fieldops.agent.state import FieldServiceState
from fieldops.db.session import SessionLocal
from fieldops.domain.services.technician_matching import TechnicianMatchingService
from fieldops.repositories.technician_repository import TechnicianRepository

logger = logging.getLogger(__name__)


def match_technicians_node(state: FieldServiceState) -> dict[str, Any]:
    """Node evaluating technician candidates using deterministic domain matching rules.

    Reads:
        state["location"]
        state["required_skills"]

    Returns:
        candidate_technician_ids: list[int]
        matching_status: str
        workflow_status: str
    """
    request_id = state.get("request_id")
    logger.info("Node [match_technicians] started: request_id=%s", request_id)

    location = state.get("location")
    required_skills = state.get("required_skills")

    with SessionLocal() as session:
        repo = TechnicianRepository(session)
        service = TechnicianMatchingService(repo)
        result = service.match_technicians(
            location=location,
            required_skills=required_skills,
        )

    # Determine next workflow status expressing business progress
    if result.matching_status == "matched":
        workflow_status = "ready_for_scheduling"
    elif result.matching_status == "needs_location":
        workflow_status = "needs_location"
    elif result.matching_status == "needs_skill_information":
        workflow_status = "needs_skill_information"
    elif result.matching_status == "no_candidates":
        workflow_status = "no_technician_available"
    else:
        workflow_status = state.get("workflow_status", "service_request_created")

    logger.info(
        "Node [match_technicians] completed: request_id=%s, matching_status=%s, workflow_status=%s, candidate_ids=%s",
        request_id,
        result.matching_status,
        workflow_status,
        result.candidate_technician_ids,
    )

    return {
        "candidate_technician_ids": result.candidate_technician_ids,
        "matching_status": result.matching_status,
        "workflow_status": workflow_status,
    }
