"""Structured logging, latency timing, correlation tracking, and sensitive data redaction."""

import contextlib
from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, Generator

logger = logging.getLogger("fieldops")


# ==============================================================================
# Sensitive Data Redaction
# ==============================================================================

def redact_email(email: str | None) -> str:
    """Mask email address (e.g. alice@example.com -> a***e@example.com)."""
    if not email or "@" not in email:
        return "[EMPTY]"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def redact_phone(phone: str | None) -> str:
    """Mask phone number keeping only the final 4 digits."""
    if not phone:
        return "[EMPTY]"
    clean = re.sub(r"\s+", "", str(phone))
    if len(clean) <= 4:
        return "****"
    return "*" * (len(clean) - 4) + clean[-4:]


def sanitize_message(message: str | None, max_preview: int = 40) -> dict[str, Any]:
    """Sanitize customer raw text returning length and safe preview."""
    if not message:
        return {"length": 0, "preview": ""}
    length = len(message)
    preview = message[:max_preview] + ("..." if length > max_preview else "")
    return {"length": length, "preview": preview}


def redact_sensitive_text(text: str) -> str:
    """Mask credentials, tokens, and database/redis passwords in raw strings."""
    if not text:
        return text

    # Mask database connection passwords: protocol://user:pass@host -> protocol://user:***@host
    redacted = re.sub(
        r"(://[^:]+:)([^@]+)(@)",
        r"\1***\3",
        text,
    )
    # Mask redis standalone password: :password@host -> :***@host
    redacted = re.sub(
        r"(://:)([^@]+)(@)",
        r"\1***\3",
        redacted,
    )
    # Mask Bearer tokens: Bearer sk-... or Bearer xyz
    redacted = re.sub(
        r"(Bearer\s+)([A-Za-z0-9_\-\.]{6,})",
        r"\1***REDACTED***",
        redacted,
        flags=re.IGNORECASE,
    )
    # Mask OpenAI API Keys: sk-...
    redacted = re.sub(
        r"(sk-[A-Za-z0-9_\-]{20,})",
        r"sk-***REDACTED***",
        redacted,
    )
    return redacted


# ==============================================================================
# JSON Structured Formatter
# ==============================================================================

class JsonFormatter(logging.Formatter):
    """Format logging records into JSON objects for structured log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": redact_sensitive_text(record.getMessage()),
        }

        # Extract structured event metadata if provided via extra
        if hasattr(record, "event"):
            log_data["event"] = getattr(record, "event")
        if hasattr(record, "request_id"):
            log_data["request_id"] = getattr(record, "request_id")
        if hasattr(record, "service_request_id"):
            log_data["service_request_id"] = getattr(record, "service_request_id")
        if hasattr(record, "appointment_id"):
            log_data["appointment_id"] = getattr(record, "appointment_id")
        if hasattr(record, "workflow_status"):
            log_data["workflow_status"] = getattr(record, "workflow_status")
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = getattr(record, "duration_ms")
        if hasattr(record, "error_type"):
            log_data["error_type"] = getattr(record, "error_type")
        if hasattr(record, "retryable"):
            log_data["retryable"] = getattr(record, "retryable")

        # Include any arbitrary extra context attached to record
        if hasattr(record, "extra_context") and isinstance(record.extra_context, dict):
            for k, v in record.extra_context.items():
                if k not in log_data:
                    log_data[k] = v

        return json.dumps(log_data, default=str, ensure_ascii=False)


def emit_event(
    event: str,
    level: str = "info",
    logger_instance: logging.Logger | None = None,
    message: str | None = None,
    request_id: str | None = None,
    **kwargs: Any,
) -> None:
    """Emit a structured event with standardized naming and attributes."""
    log_func = getattr(logger_instance or logger, level.lower(), logger.info)
    msg = message or f"Event: {event}"
    extra_payload = {
        "event": event,
        "request_id": request_id,
        **kwargs,
    }
    log_func(msg, extra={"event": event, "request_id": request_id, "extra_context": extra_payload})


# ==============================================================================
# Latency Context Manager
# ==============================================================================

@contextlib.contextmanager
def log_operation(
    operation: str,
    request_id: str | None = None,
    service_request_id: int | None = None,
    node: str | None = None,
    extra_context: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager measuring execution latency and emitting structured logs with correlation ID."""
    context: dict[str, Any] = {
        "operation": operation,
        "request_id": request_id or "unspecified",
        "service_request_id": service_request_id,
        "node": node,
    }
    if extra_context:
        context.update(extra_context)

    start_time = time.perf_counter()
    logger.info("Started [%s] context=%s", operation, context)
    try:
        yield context
    except Exception as e:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        context["duration_ms"] = duration_ms
        context["error_type"] = type(e).__name__
        context["error_message"] = str(e)
        logger.error("Failed [%s] context=%s", operation, context)
        raise
    else:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        context["duration_ms"] = duration_ms
        logger.info("Completed [%s] context=%s", operation, context)
