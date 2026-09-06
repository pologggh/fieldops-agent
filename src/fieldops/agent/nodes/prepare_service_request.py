import logging
from typing import Any

from fieldops.agent.state import FieldServiceState

logger = logging.getLogger(__name__)


def prepare_service_request_node(state: FieldServiceState) -> dict[str, Any]:
    """Consolidation node preparing the request state for subsequent business phases.

    Confirms state readiness.
    Does NOT write to the database and does NOT create ORM objects.
    """
    request_id = state.get("request_id")
    logger.info("Node [prepare_service_request] started: request_id=%s", request_id)

    current_status = state.get("workflow_status")
    if current_status == "validated":
        next_status = "ready_for_service_request"
    else:
        next_status = "needs_information"

    logger.info(
        "Node [prepare_service_request] completed: request_id=%s, workflow_status=%s",
        request_id,
        next_status,
    )

    return {
        "workflow_status": next_status,
    }
