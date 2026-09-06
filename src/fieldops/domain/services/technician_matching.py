import logging
from dataclasses import dataclass
from typing import Literal

from fieldops.repositories.technician_repository import TechnicianRepository

logger = logging.getLogger(__name__)

MatchingStatus = Literal[
    "matched",
    "no_candidates",
    "needs_location",
    "needs_skill_information",
]


@dataclass(frozen=True)
class TechnicianMatchingResult:
    """Outcome of deterministic technician candidate evaluation."""

    candidate_technician_ids: list[int]
    matching_status: MatchingStatus


class TechnicianMatchingService:
    """Domain service that filters technician candidates using deterministic business rules."""

    def __init__(self, repository: TechnicianRepository) -> None:
        self.repository = repository

    def match_technicians(
        self,
        location: str | None,
        required_skills: list[str] | None,
    ) -> TechnicianMatchingResult:
        """Evaluate and filter candidate technicians based on V1 deterministic matching rules.

        Rules:
        1. Missing/empty location -> needs_location (IDs: [])
        2. Missing/empty required_skills -> needs_skill_information (IDs: [])
        3. Technician status must be active.
        4. Normalized service area matches requested location (case-insensitive).
        5. Normalized required_skills must be a subset of technician skills:
           requested_skills <= technician_skills.
        6. If 1+ technicians qualify -> 'matched' with all IDs.
        7. If 0 technicians qualify -> 'no_candidates' with empty IDs.
        """
        # Rule 1: Check location
        if not location or not location.strip():
            logger.info("Technician matching skipped: missing location.")
            return TechnicianMatchingResult(
                candidate_technician_ids=[],
                matching_status="needs_location",
            )

        # Rule 2: Check required skills
        normalized_required = {
            s.strip().casefold()
            for s in (required_skills or [])
            if s and s.strip()
        }
        if not normalized_required:
            logger.info("Technician matching skipped: missing required skills.")
            return TechnicianMatchingResult(
                candidate_technician_ids=[],
                matching_status="needs_skill_information",
            )

        norm_location = location.strip()
        logger.info(
            "Querying active technicians in area='%s' with skills=%s",
            norm_location,
            sorted(normalized_required),
        )

        # Query active technicians stationed in the area with skills loaded
        technicians = self.repository.find_active_by_area_with_skills(norm_location)

        matched_ids: list[int] = []
        for tech in technicians:
            # Rule 3: status active (enforced in repository query, verified here)
            if tech.status != "active":
                continue

            # Rule 5: required skills <= technician skills
            tech_skills = {
                ts.skill.strip().casefold()
                for ts in tech.skills
                if ts.skill and ts.skill.strip()
            }
            if normalized_required.issubset(tech_skills):
                matched_ids.append(tech.id)

        if not matched_ids:
            logger.info(
                "No active technicians matched in area='%s' with skills=%s",
                norm_location,
                sorted(normalized_required),
            )
            return TechnicianMatchingResult(
                candidate_technician_ids=[],
                matching_status="no_candidates",
            )

        logger.info(
            "Matched %d technician candidate(s): ids=%s",
            len(matched_ids),
            matched_ids,
        )
        return TechnicianMatchingResult(
            candidate_technician_ids=matched_ids,
            matching_status="matched",
        )
