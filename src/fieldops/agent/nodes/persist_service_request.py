import logging
from typing import Any

from fieldops.agent.state import FieldServiceState
from fieldops.application.persistence import persist_customer_and_service_request

logger = logging.getLogger(__name__)


def persist_service_request_node(state: FieldServiceState) -> dict[str, Any]:
    """Atomically find/create customer and create service request within a single transaction.

    Updates:
        customer_id: int
        service_request_id: int
        workflow_status: "service_request_created"
    """
    request_id = state.get("request_id")
    logger.info("Node [persist_service_request] started: request_id=%s", request_id)

    customer_id, service_request_id = persist_customer_and_service_request(
        customer_name=state.get("customer_name") or "Unknown",
        customer_email=state.get("customer_email", ""),
        customer_phone=state.get("customer_phone"),
        raw_message=state.get("raw_message", ""),
        service_type=state.get("service_type") or "Other",
        urgency=state.get("urgency") or "medium",
        location=state.get("location") or "Unknown",
    )

    logger.info(
        "Node [persist_service_request] completed: request_id=%s, customer_id=%d, service_request_id=%d",
        request_id,
        customer_id,
        service_request_id,
    )

    return {
        "customer_id": customer_id,
        "service_request_id": service_request_id,
        "workflow_status": "service_request_created",
    }
