import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class AppointmentProposal(TypedDict, total=False):
    """Structured representation of a recommended appointment proposal."""

    technician_id: int
    technician_name: str | None
    start_time: str
    end_time: str
    service_request_id: int | None


class AppointmentProposalService:
    """Domain service for deterministically selecting a recommended appointment proposal.

    Deterministic policy:
    1. Primary: Earliest available appointment start time (ASC).
    2. Secondary (tie-breaker): Lowest technician_id (ASC).
    """

    @staticmethod
    def select_proposal(
        available_options: list[dict[str, Any]],
        service_request_id: int | None = None,
        technician_names: dict[int, str] | None = None,
    ) -> AppointmentProposal | None:
        """Select the optimal appointment proposal from available candidate options.

        Args:
            available_options: List of non-conflicting appointment slot dictionaries.
            service_request_id: Associated ServiceRequest ID.
            technician_names: Optional lookup map of technician_id -> display name.

        Returns:
            AppointmentProposal dictionary or None if no options exist.
        """
        if not available_options:
            logger.info("Cannot select proposal: available_options is empty.")
            return None

        # Deterministic sort: (start_time ASC, technician_id ASC)
        sorted_options = sorted(
            available_options,
            key=lambda opt: (str(opt["start_time"]), int(opt["technician_id"])),
        )

        selected = sorted_options[0]
        tech_id = int(selected["technician_id"])
        tech_name = technician_names.get(tech_id) if technician_names else None

        proposal: AppointmentProposal = {
            "technician_id": tech_id,
            "technician_name": tech_name,
            "start_time": str(selected["start_time"]),
            "end_time": str(selected["end_time"]),
            "service_request_id": service_request_id,
        }

        logger.info(
            "Selected appointment proposal deterministically: tech_id=%d, start=%s, end=%s",
            tech_id,
            proposal["start_time"],
            proposal["end_time"],
        )
        return proposal
