import time
import logging
from typing import Any

from fieldops.core.exceptions import LLMTimeoutError
from fieldops.llm.exceptions import LLMCallError
from fieldops.llm.schemas import ParsedServiceRequest

logger = logging.getLogger(__name__)

# Global failure injection state for deterministic testing
_FAILURE_CONFIG: dict[str, Any] = {
    "delay_seconds": 0.0,
    "fail_first_n": 0,
    "permanent_failure": False,
    "timeout_error": False,
    "current_failure_count": 0,
}


def set_failure_injection(
    delay_seconds: float = 0.0,
    fail_first_n: int = 0,
    permanent_failure: bool = False,
    timeout_error: bool = False,
) -> None:
    """Configure deterministic failure injection parameters for FakeLLM."""
    global _FAILURE_CONFIG
    _FAILURE_CONFIG = {
        "delay_seconds": delay_seconds,
        "fail_first_n": fail_first_n,
        "permanent_failure": permanent_failure,
        "timeout_error": timeout_error,
        "current_failure_count": 0,
    }
    logger.info("Configured FakeLLM failure injection: %s", _FAILURE_CONFIG)


def reset_failure_injection() -> None:
    """Reset all failure injection parameters to normal operational state."""
    global _FAILURE_CONFIG
    _FAILURE_CONFIG = {
        "delay_seconds": 0.0,
        "fail_first_n": 0,
        "permanent_failure": False,
        "timeout_error": False,
        "current_failure_count": 0,
    }


def parse_with_fake_llm(message: str) -> ParsedServiceRequest:
    """Fast, deterministic pseudo-LLM parser for load and reliability testing without external API calls."""
    global _FAILURE_CONFIG

    # 1. Inject artificial latency if configured
    delay = _FAILURE_CONFIG.get("delay_seconds", 0.0)
    if delay > 0:
        logger.debug("Simulating LLM latency of %.2fs", delay)
        time.sleep(delay)

    # 2. Inject timeout failure if configured
    if _FAILURE_CONFIG.get("timeout_error", False):
        raise LLMTimeoutError("Simulated LLM API timeout during load test.")

    # 3. Inject permanent failure if configured
    if _FAILURE_CONFIG.get("permanent_failure", False):
        raise LLMCallError("Simulated permanent LLM API error (500).", retryable=False)

    # 4. Inject transient failure if configured
    fail_first_n = _FAILURE_CONFIG.get("fail_first_n", 0)
    current_count = _FAILURE_CONFIG.get("current_failure_count", 0)
    if current_count < fail_first_n:
        _FAILURE_CONFIG["current_failure_count"] = current_count + 1
        logger.warning(
            "Simulating transient LLM failure (%d/%d)",
            current_count + 1,
            fail_first_n,
        )
        raise LLMCallError("Simulated transient LLM error (503).", retryable=True)

    # 5. Deterministic keyword-based structured extraction
    msg = message.lower()

    # Determine service type and skills
    if any(k in msg for k in ("hvac", "ac", "air condition", "heating", "cooling", "thermostat")):
        service_type = "HVAC"
        skills = ["HVAC"]
    elif any(k in msg for k in ("plumb", "pipe", "leak", "sink", "water", "drain")):
        service_type = "Plumbing"
        skills = ["Plumbing"]
    elif any(k in msg for k in ("electric", "wire", "power", "outlet", "circuit")):
        service_type = "Electrical"
        skills = ["Electrical"]
    elif any(k in msg for k in ("network", "wifi", "router", "internet", "ethernet")):
        service_type = "Networking"
        skills = ["Networking"]
    else:
        service_type = "Appliance Repair"
        skills = []

    # Determine location
    location = None
    for loc in ("Shinjuku", "Shibuya", "Yokohama", "Roppongi", "Minato", "Meguro", "Chiyoda"):
        if loc.lower() in msg:
            location = loc
            break

    # Determine urgency
    if any(k in msg for k in ("emergency", "fire", "burning", "flooding", "danger")):
        urgency = "emergency"
    elif any(k in msg for k in ("urgent", "asap", "immediately", "right away")):
        urgency = "high"
    elif any(k in msg for k in ("tomorrow", "soon", "next day")):
        urgency = "medium"
    else:
        urgency = "low"

    # Determine preferred time
    preferred_time = None
    if "afternoon" in msg:
        preferred_time = "this afternoon"
    elif "morning" in msg:
        preferred_time = "tomorrow morning"
    elif "evening" in msg:
        preferred_time = "this evening"
    elif "tomorrow" in msg:
        preferred_time = "tomorrow"

    return ParsedServiceRequest(
        customer_intent="request_service",
        service_type=service_type,
        urgency=urgency,
        location=location,
        preferred_time=preferred_time,
        required_skills=skills,
        problem_description=message[:200].strip(),
    )
