"""OpenTelemetry distributed tracing setup, node wrappers, and span context management."""

import contextlib
import logging
import os
import time
from typing import Any, Generator

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Span, StatusCode

from fieldops.observability.metrics import (
    NODE_DURATION_SECONDS,
    NODE_FAILURES_TOTAL,
)

logger = logging.getLogger(__name__)

# Tracer instance
_tracer = trace.get_tracer("fieldops.tracer")


def setup_tracing(app=None) -> TracerProvider:
    """Initialize OpenTelemetry tracer provider, exporters, and optional FastAPI instrumentation."""
    resource = Resource.create({
        "service.name": "fieldops-agent",
        "service.version": "0.1.0",
        "deployment.environment": os.getenv("APP_ENV", "development"),
    })

    provider = TracerProvider(resource=resource)

    # Configure exporter: OTLP if endpoint provided, otherwise lightweight console/debug exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTLP Trace exporter configured for endpoint: %s", otlp_endpoint)
        except Exception as e:
            logger.warning("Failed to initialize OTLP exporter, falling back to console: %s", e)
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif os.getenv("OTEL_TRACING_CONSOLE", "false").lower() in ("true", "1"):
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    # Instrument FastAPI application
    if app is not None:
        try:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=provider,
                excluded_urls="health,ready,metrics",
            )
            logger.info("FastAPI OpenTelemetry instrumentation initialized.")
        except Exception as e:
            logger.warning("Failed to instrument FastAPI app: %s", e)

    return provider


def get_tracer() -> trace.Tracer:
    """Return the application OpenTelemetry tracer."""
    return trace.get_tracer("fieldops.tracer")


@contextlib.contextmanager
def trace_node(node_name: str, state: dict[str, Any]) -> Generator[Span, None, None]:
    """Context manager tracing the execution of a LangGraph node.

    Emits OpenTelemetry span with request_id and status attributes, and records
    node latency and failure metrics without polluting Prometheus with high-cardinality labels.
    """
    tracer = get_tracer()
    span_name = f"fieldops.node.{node_name}"
    request_id = state.get("request_id") or "unspecified"
    initial_status = state.get("workflow_status") or "unknown"

    start_time = time.perf_counter()

    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("fieldops.node.name", node_name)
        span.set_attribute("fieldops.request_id", request_id)
        span.set_attribute("fieldops.workflow_status.initial", initial_status)

        try:
            yield span
        except Exception as exc:
            duration = time.perf_counter() - start_time
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            NODE_FAILURES_TOTAL.labels(node=node_name).inc()
            NODE_DURATION_SECONDS.labels(node=node_name).observe(duration)
            raise
        else:
            duration = time.perf_counter() - start_time
            span.set_status(StatusCode.OK)
            NODE_DURATION_SECONDS.labels(node=node_name).observe(duration)


@contextlib.contextmanager
def trace_llm_call(model: str, request_id: str | None = None) -> Generator[dict[str, Any], None, None]:
    """Context manager tracing an LLM parse call."""
    tracer = get_tracer()
    span_name = "fieldops.llm.parse_service_request"
    start_time = time.perf_counter()

    metadata: dict[str, Any] = {
        "model": model,
        "request_id": request_id,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "estimated_cost": None,
    }

    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("llm.provider", "openai")
        span.set_attribute("llm.model", model)
        if request_id:
            span.set_attribute("fieldops.request_id", request_id)

        try:
            yield metadata
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise
        else:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            span.set_status(StatusCode.OK)
            span.set_attribute("llm.duration_ms", duration_ms)
            if metadata.get("input_tokens") is not None:
                span.set_attribute("llm.usage.prompt_tokens", metadata["input_tokens"])
            if metadata.get("output_tokens") is not None:
                span.set_attribute("llm.usage.completion_tokens", metadata["output_tokens"])
            if metadata.get("total_tokens") is not None:
                span.set_attribute("llm.usage.total_tokens", metadata["total_tokens"])
            if metadata.get("estimated_cost") is not None:
                span.set_attribute("llm.usage.estimated_cost_usd", metadata["estimated_cost"])


@contextlib.contextmanager
def trace_integration_operation(
    provider: str,
    operation: str,
    local_resource_id: int | None = None,
    retry_count: int = 0,
) -> Generator[Span, None, None]:
    """Context manager tracing an external integration call (calendar sync or email send)."""
    tracer = get_tracer()
    span_name = f"fieldops.integration.{operation}"
    start_time = time.perf_counter()

    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("integration.provider", provider)
        span.set_attribute("integration.operation", operation)
        if local_resource_id is not None:
            span.set_attribute("integration.local_resource_id", str(local_resource_id))
        span.set_attribute("integration.retry_count", retry_count)

        try:
            yield span
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            span.set_attribute("integration.duration_ms", duration_ms)
            span.set_attribute("integration.status", "failed")
            raise
        else:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            span.set_status(StatusCode.OK)
            span.set_attribute("integration.duration_ms", duration_ms)
            span.set_attribute("integration.status", "success")


@contextlib.contextmanager
def trace_intake_operation(
    operation: str,
    source: str,
    external_message_id: str | None = None,
) -> Generator[Span, None, None]:
    """Context manager tracing an inbound request normalization or processing operation."""
    tracer = get_tracer()
    span_name = f"fieldops.intake.{operation}"
    start_time = time.perf_counter()

    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("intake.operation", operation)
        span.set_attribute("intake.source", source)
        if external_message_id is not None:
            span.set_attribute("intake.external_message_id", str(external_message_id))

        try:
            yield span
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            span.set_attribute("intake.duration_ms", duration_ms)
            span.set_attribute("intake.status", "failed")
            raise
        else:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            span.set_status(StatusCode.OK)
            span.set_attribute("intake.duration_ms", duration_ms)
            span.set_attribute("intake.status", "success")


@contextlib.contextmanager
def trace_conversation_operation(
    operation: str,
    conversation_id: int | None = None,
    action: str | None = None,
) -> Generator[Span, None, None]:
    """Context manager tracing conversational agent operations (turn, parse, validate, confirm)."""
    tracer = get_tracer()
    span_name = f"fieldops.conversation.{operation}"
    start_time = time.perf_counter()

    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("conversation.operation", operation)
        if conversation_id is not None:
            span.set_attribute("conversation.id", conversation_id)
        if action is not None:
            span.set_attribute("conversation.action", action)

        try:
            yield span
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            span.set_attribute("conversation.duration_ms", duration_ms)
            span.set_attribute("conversation.status", "failed")
            raise
        else:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            span.set_status(StatusCode.OK)
            span.set_attribute("conversation.duration_ms", duration_ms)
            span.set_attribute("conversation.status", "success")



