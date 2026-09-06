"""Parse request node extracting structured fields from natural language messages with failure recovery."""

import logging
from typing import Any

from fieldops.agent.state import FieldServiceState
from fieldops.core.exceptions import LLMTimeoutError
from fieldops.core.logging import log_operation
from fieldops.llm import EmptyMessageError, LLMCallError, parse_service_request

logger = logging.getLogger(__name__)


def parse_request_node(state: FieldServiceState) -> dict[str, Any]:
    """Extract structured information from natural language raw_message.

    Handles transient timeouts and schema failures gracefully, setting
    explicit error flags and workflow_status instead of inventing fallback data.
    Re-raises client input errors (EmptyMessageError) immediately.
    """
    request_id = state.get("request_id")
    raw_message = state.get("raw_message", "")

    try:
        with log_operation("node.parse_request", request_id=request_id, node="parse_request"):
            parsed = parse_service_request(raw_message)
    except EmptyMessageError:
        # Input validation error: re-raise directly for HTTP 400 response
        raise
    except LLMTimeoutError as e:
        logger.error("LLM timeout in parse_request: request_id=%s, error=%s", request_id, e)
        return {
            "workflow_status": "llm_failed",
            "error_code": "llm_timeout",
            "error_message": str(e),
            "failed_step": "parse_request",
            "retryable": True,
        }
    except LLMCallError as e:
        logger.error("LLM call error in parse_request: request_id=%s, error=%s", request_id, e)
        err_msg = str(e).lower()
        if "refused" in err_msg:
            code = "model_refusal"
            retryable = False
        elif "structured output" in err_msg:
            code = "structured_output_invalid"
            retryable = False
        else:
            code = "llm_call_failed"
            retryable = getattr(e, "retryable", False)

        return {
            "workflow_status": "llm_failed",
            "error_code": code,
            "error_message": str(e),
            "failed_step": "parse_request",
            "retryable": retryable,
        }
    except Exception as e:
        logger.error("Unexpected error in parse_request: request_id=%s, error=%s", request_id, e)
        return {
            "workflow_status": "llm_failed",
            "error_code": "llm_unknown_error",
            "error_message": str(e),
            "failed_step": "parse_request",
            "retryable": False,
        }

    return {
        "service_type": parsed.service_type,
        "urgency": parsed.urgency,
        "location": parsed.location,
        "required_skills": parsed.required_skills,
        "preferred_time": parsed.preferred_time,
        "problem_description": parsed.problem_description,
        "workflow_status": "parsed",
        "error_code": None,
        "error_message": None,
        "failed_step": None,
        "retryable": False,
    }
