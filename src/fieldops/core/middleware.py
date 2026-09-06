"""HTTP middleware for correlation ID tracking, latency timing, and metrics instrumentation."""

from contextvars import ContextVar
import logging
import time
import uuid
import re
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fieldops.core.logging import emit_event
from fieldops.observability.metrics import (
    HTTP_ERRORS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)

logger = logging.getLogger("fieldops.http")

# Global context variable holding current request correlation identifier
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="unspecified")


def get_current_request_id() -> str:
    """Return the active request correlation identifier from context."""
    return correlation_id_ctx.get()


def _normalize_metric_path(path: str) -> str:
    """Normalize parameterized URL paths to prevent cardinality explosion in Prometheus labels."""
    p = re.sub(r"/service-requests/[^/]+/approval", "/service-requests/{request_id}/approval", path)
    p = re.sub(r"/appointments/\d+(/[a-z]+)?", r"/appointments/{id}\1", p)
    return p


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware extracting/generating request correlation IDs and instrumenting HTTP metrics."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 1. Extract X-Request-ID or generate new correlation ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = correlation_id_ctx.set(request_id)

        # Store on request.state for convenient route access
        request.state.request_id = request_id

        # Normalize path for metrics to avoid cardinality explosion
        path = request.url.path
        metric_path = _normalize_metric_path(path)
        method = request.method

        start_time = time.perf_counter()

        # Emit structured log event for received request (exclude internal scrape/probe paths)
        if not path.startswith(("/health", "/ready", "/metrics")):
            emit_event(
                event="request.received",
                level="info",
                logger_instance=logger,
                request_id=request_id,
                method=method,
                path=path,
            )

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000, 2)
            HTTP_REQUESTS_TOTAL.labels(method=method, path=metric_path, status_code="500").inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=metric_path).observe(duration_s)
            HTTP_ERRORS_TOTAL.labels(method=method, path=metric_path, error_type=type(exc).__name__).inc()
            emit_event(
                event="request.failed",
                level="error",
                logger_instance=logger,
                request_id=request_id,
                method=method,
                path=path,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            correlation_id_ctx.reset(token)
            raise

        duration_s = time.perf_counter() - start_time
        duration_ms = round(duration_s * 1000, 2)

        # Record HTTP metrics (using low-cardinality path & status)
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            path=metric_path,
            status_code=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=metric_path).observe(duration_s)

        if status_code >= 400:
            HTTP_ERRORS_TOTAL.labels(
                method=method,
                path=metric_path,
                error_type=f"HTTP_{status_code}",
            ).inc()

        # Attach correlation ID to response headers
        response.headers["X-Request-ID"] = request_id

        if not path.startswith(("/health", "/ready", "/metrics")):
            emit_event(
                event="request.completed",
                level="info",
                logger_instance=logger,
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
            )

        correlation_id_ctx.reset(token)
        return response
