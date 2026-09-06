import logging
from typing import Any

from fieldops.agent.state import FieldServiceState
from fieldops.db.session import SessionLocal
from fieldops.domain.services.scheduling import SchedulingService
from fieldops.domain.services.time_window_parser import TimeWindowParser
from fieldops.repositories.appointment_repository import AppointmentRepository

logger = logging.getLogger(__name__)


def check_schedule_node(state: FieldServiceState) -> dict[str, Any]:
    """Node evaluating technician schedule availability against existing appointments.

    Reads:
        state["preferred_time"]
        state["candidate_technician_ids"]

    Returns:
        requested_window_start: str | None
        requested_window_end: str | None
        available_options: list[dict[str, Any]]
        scheduling_status: str
        workflow_status: str
    """
    request_id = state.get("request_id")
    logger.info("Node [check_schedule] started: request_id=%s", request_id)

    preferred_time = state.get("preferred_time")
    candidate_ids = state.get("candidate_technician_ids", [])

    parser = TimeWindowParser()
    window = parser.parse(preferred_time)

    # 1. If preferred_time cannot be parsed into a computable window
    if window is None:
        logger.info(
            "preferred_time '%s' not supported or missing; clarification required.",
            preferred_time,
        )
        return {
            "requested_window_start": None,
            "requested_window_end": None,
            "available_options": [],
            "scheduling_status": "needs_time_clarification",
            "workflow_status": "needs_time_clarification",
        }

    window_start_iso = window.start_time.isoformat()
    window_end_iso = window.end_time.isoformat()

    # 2. If no candidate technicians are present
    if not candidate_ids:
        logger.info("No candidate technicians available for schedule checking.")
        return {
            "requested_window_start": window_start_iso,
            "requested_window_end": window_end_iso,
            "available_options": [],
            "scheduling_status": "no_available_slots",
            "workflow_status": "no_available_slots",
        }

    # 3. Check availability using PostgreSQL AppointmentRepository
    with SessionLocal() as session:
        repo = AppointmentRepository(session)
        service = SchedulingService(repo)
        result = service.check_availability(
            candidate_technician_ids=candidate_ids,
            window=window,
        )

    # 4. Determine final workflow status
    if result.scheduling_status == "schedule_options_ready":
        workflow_status = "schedule_options_ready"
    else:
        workflow_status = "no_available_slots"

    logger.info(
        "Node [check_schedule] completed: request_id=%s, options_count=%d, status=%s",
        request_id,
        len(result.available_options),
        workflow_status,
    )

    return {
        "requested_window_start": window_start_iso,
        "requested_window_end": window_end_iso,
        "available_options": result.available_options,
        "scheduling_status": result.scheduling_status,
        "workflow_status": workflow_status,
    }
