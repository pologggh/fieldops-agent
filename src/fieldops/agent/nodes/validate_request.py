import logging
from typing import Any

from fieldops.agent.state import FieldServiceState

logger = logging.getLogger(__name__)

ALLOWED_SERVICE_TYPES = {
    "HVAC",
    "Plumbing",
    "Electrical",
    "Networking",
    "Appliance Repair",
    "Other",
}

ALLOWED_URGENCY_LEVELS = {
    "low",
    "medium",
    "high",
    "emergency",
}


def validate_request_node(state: FieldServiceState) -> dict[str, Any]:
    """Validate parsed request using deterministic Python rules (no LLM).

    Distinguishes between:
    - Fatal errors (e.g. invalid service_type, invalid urgency, empty message):
      Causes workflow_status = "needs_information" and stops subsequent preparation.
    - Non-fatal missing info (e.g. missing location):
      Recorded in validation_errors for downstream awareness, but workflow_status = "validated".
    """
    request_id = state.get("request_id")
    logger.info("Node [validate_request] started: request_id=%s", request_id)

    errors: list[str] = list(state.get("validation_errors", []))
    has_fatal_error = False

    # 1. raw_message validation
    raw_message = (state.get("raw_message") or "").strip()
    if not raw_message:
        errors.append("raw_message cannot be empty.")
        has_fatal_error = True

    # 2. service_type validation
    service_type = state.get("service_type")
    if not service_type:
        errors.append("service_type is missing.")
        has_fatal_error = True
    elif service_type not in ALLOWED_SERVICE_TYPES:
        errors.append(
            f"Invalid service_type '{service_type}'. Allowed: {sorted(ALLOWED_SERVICE_TYPES)}"
        )
        has_fatal_error = True

    # 3. urgency validation
    urgency = state.get("urgency")
    if not urgency:
        errors.append("urgency is missing.")
        has_fatal_error = True
    elif urgency.lower() not in ALLOWED_URGENCY_LEVELS:
        errors.append(
            f"Invalid urgency '{urgency}'. Allowed: {sorted(ALLOWED_URGENCY_LEVELS)}"
        )
        has_fatal_error = True

    # 4. required_skills validation
    required_skills = state.get("required_skills")
    if not isinstance(required_skills, list) or not all(
        isinstance(s, str) for s in required_skills
    ):
        errors.append("required_skills must be a list of strings.")
        has_fatal_error = True

    # 5. location validation (non-fatal missing information)
    location = state.get("location")
    if not location or not str(location).strip():
        errors.append("missing_location: Service location was not specified in the request.")

    workflow_status = "needs_information" if has_fatal_error else "validated"

    logger.info(
        "Node [validate_request] completed: request_id=%s, workflow_status=%s, errors=%s",
        request_id,
        workflow_status,
        errors,
    )

    return {
        "validation_errors": errors,
        "workflow_status": workflow_status,
    }
