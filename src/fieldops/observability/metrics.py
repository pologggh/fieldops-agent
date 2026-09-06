"""Prometheus metrics instrumentation with strictly controlled low-cardinality labels."""

from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ==============================================================================
# 1. HTTP Layer Metrics
# ==============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "fieldops_http_requests_total",
    "Total count of incoming HTTP requests.",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "fieldops_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_ERRORS_TOTAL = Counter(
    "fieldops_http_errors_total",
    "Total count of HTTP request errors.",
    ["method", "path", "error_type"],
)

# ==============================================================================
# 2. LangGraph Workflow Metrics
# ==============================================================================

WORKFLOWS_TOTAL = Counter(
    "fieldops_workflows_total",
    "Total number of workflow runs partitioned by final business outcome.",
    ["result"],
)

WORKFLOW_DURATION_SECONDS = Histogram(
    "fieldops_workflow_duration_seconds",
    "Duration of complete field service workflow execution in seconds.",
    ["result"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# Phase 28: Workflow Intelligence & Resilience Metrics
WORKFLOW_DECISIONS_TOTAL = Counter(
    "fieldops_workflow_decisions_total",
    "Total decisions evaluated across workflow stages.",
    ["decision_type", "action"],
)

WORKFLOW_ROUTES_TOTAL = Counter(
    "fieldops_workflow_routes_total",
    "Total dynamic routes traversed between workflow subgraphs/nodes.",
    ["from_stage", "to_route"],
)

WORKFLOW_RECOVERY_TOTAL = Counter(
    "fieldops_workflow_recovery_total",
    "Total recovery classifications evaluated partitioned by error class and action.",
    ["error_class", "action"],
)

WORKFLOW_INVARIANT_FAILURES_TOTAL = Counter(
    "fieldops_workflow_invariant_failures_total",
    "Total workflow invariant or state transition guard violations detected.",
    ["invariant_name"],
)

WORKFLOW_HUMAN_REVIEWS_TOTAL = Counter(
    "fieldops_workflow_human_reviews_total",
    "Total HITL reviews initiated partitioned by required review level.",
    ["review_level", "review_type"],
)

WORKFLOW_DEAD_ENDS_TOTAL = Counter(
    "fieldops_workflow_dead_ends_total",
    "Total dead-end routing terminations detected.",
    ["stage"],
)

WORKFLOW_STEP_COUNT = Histogram(
    "fieldops_workflow_step_count",
    "Distribution of step counts required to complete workflows.",
    buckets=(1, 2, 4, 6, 8, 10, 15, 20, 25),
)

WORKFLOW_ACTIVE_DURATION_SECONDS = Histogram(
    "fieldops_workflow_active_duration_seconds",
    "Active processing duration of workflow excluding waiting on human review.",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ==============================================================================
# 3. LangGraph Node Metrics
# ==============================================================================

NODE_DURATION_SECONDS = Histogram(
    "fieldops_node_duration_seconds",
    "Execution duration of individual LangGraph nodes in seconds.",
    ["node"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

NODE_FAILURES_TOTAL = Counter(
    "fieldops_node_failures_total",
    "Total number of failures encountered inside individual LangGraph nodes.",
    ["node"],
)

# ==============================================================================
# 4. LLM Usage & Cost Metrics
# ==============================================================================

LLM_REQUESTS_TOTAL = Counter(
    "fieldops_llm_requests_total",
    "Total LLM API requests partitioned by model and outcome status.",
    ["model", "status"],
)

LLM_FAILURES_TOTAL = Counter(
    "fieldops_llm_failures_total",
    "Total count of LLM invocation failures.",
    ["model", "error_type"],
)

LLM_INPUT_TOKENS_TOTAL = Counter(
    "fieldops_llm_input_tokens_total",
    "Cumulative prompt/input tokens consumed by LLM invocations.",
    ["model"],
)

LLM_OUTPUT_TOKENS_TOTAL = Counter(
    "fieldops_llm_output_tokens_total",
    "Cumulative completion/output tokens consumed by LLM invocations.",
    ["model"],
)

LLM_ESTIMATED_COST_TOTAL = Counter(
    "fieldops_llm_estimated_cost_total",
    "Estimated cumulative cost in USD for LLM usage.",
    ["model"],
)

# ==============================================================================
# 5. Scheduling & Matching Business Metrics
# ==============================================================================

MATCHING_NO_CANDIDATES_TOTAL = Counter(
    "fieldops_matching_no_candidates_total",
    "Count of requests where technician matching found zero candidates.",
)

SCHEDULING_NO_SLOTS_TOTAL = Counter(
    "fieldops_scheduling_no_slots_total",
    "Count of requests where no available schedule time slots were found.",
)

APPOINTMENT_CONFLICTS_TOTAL = Counter(
    "fieldops_appointment_conflicts_total",
    "Count of appointment finalization attempts that encountered scheduling conflicts.",
)

# ==============================================================================
# 6. Asynchronous Jobs & Outbox Metrics
# ==============================================================================

OUTBOX_PENDING = Gauge(
    "fieldops_outbox_pending",
    "Current number of pending outbox events awaiting broker dispatch.",
)

OUTBOX_PUBLISH_FAILURES_TOTAL = Counter(
    "fieldops_outbox_publish_failures_total",
    "Total number of failed attempts to publish outbox events to the message broker.",
)

NOTIFICATION_JOBS_TOTAL = Counter(
    "fieldops_notification_jobs_total",
    "Total notification jobs processed partitioned by type and status.",
    ["job_type", "status"],
)

NOTIFICATION_FAILURES_TOTAL = Counter(
    "fieldops_notification_failures_total",
    "Total notification job execution failures.",
    ["job_type"],
)

# ==============================================================================
# 7. Third-Party Integration Metrics (Phase 15)
# ==============================================================================

INTEGRATION_OPERATIONS_TOTAL = Counter(
    "fieldops_integration_operations_total",
    "Total operations invoked against third-party external providers.",
    ["provider", "operation", "result"],
)

INTEGRATION_DURATION_SECONDS = Histogram(
    "fieldops_integration_duration_seconds",
    "Execution latency of third-party integration operations in seconds.",
    ["provider", "operation"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

INTEGRATION_FAILURES_TOTAL = Counter(
    "fieldops_integration_failures_total",
    "Total failure count of third-party integration operations.",
    ["provider", "operation"],
)

EMAIL_NOTIFICATIONS_TOTAL = Counter(
    "fieldops_email_notifications_total",
    "Total email notifications dispatched partitioned by provider and status.",
    ["provider", "status"],
)

CALENDAR_SYNC_TOTAL = Counter(
    "fieldops_calendar_sync_total",
    "Total calendar synchronization operations partitioned by provider and status.",
    ["provider", "status"],
)

GOOGLE_CALENDAR_API_CALLS_TOTAL = Counter(
    "fieldops_google_calendar_api_calls_total",
    "Total Google Calendar API requests partitioned by operation and outcome status.",
    ["operation", "status"],
)

GOOGLE_CALENDAR_LATENCY_SECONDS = Histogram(
    "fieldops_google_calendar_latency_seconds",
    "Latency of Google Calendar API calls in seconds.",
    ["operation"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

CALENDAR_RECONCILIATION_DRIFT_TOTAL = Counter(
    "fieldops_calendar_reconciliation_drift_total",
    "Total detected inconsistencies between local IntegrationRecords and remote calendar events.",
    ["provider", "drift_type"],
)

# ==============================================================================
# 8. Inbound Intake Layer Metrics (Phase 16)
# ==============================================================================

INBOUND_REQUESTS_TOTAL = Counter(
    "fieldops_inbound_requests_total",
    "Total inbound service requests received by channel source and outcome result.",
    ["source", "result"],  # result: success, duplicate, failed, conflict
)

INBOUND_DUPLICATES_TOTAL = Counter(
    "fieldops_inbound_duplicates_total",
    "Total duplicate inbound requests detected by channel source.",
    ["source"],
)

INBOUND_FAILURES_TOTAL = Counter(
    "fieldops_inbound_failures_total",
    "Total inbound processing failures partitioned by channel source.",
    ["source"],
)

# ==============================================================================
# 8b. Customer Conversational Agent Metrics (Phase 22)
# ==============================================================================

CONVERSATION_TURNS_TOTAL = Counter(
    "fieldops_conversation_turns_total",
    "Total turns processed by conversational intake agent.",
    ["result"],
)

CONVERSATION_CLARIFICATIONS_TOTAL = Counter(
    "fieldops_conversation_clarifications_total",
    "Total clarifications requested by missing field category.",
    ["missing_field"],
)

CONVERSATION_SUBMISSIONS_TOTAL = Counter(
    "fieldops_conversation_submissions_total",
    "Total formal service requests submitted from conversation.",
    ["status"],
)

CONVERSATION_FAILURES_TOTAL = Counter(
    "fieldops_conversation_failures_total",
    "Total conversation turn failures.",
    ["error_type"],
)

CONVERSATION_TURN_DURATION_SECONDS = Histogram(
    "fieldops_conversation_turn_duration_seconds",
    "Processing duration of conversation turn in seconds.",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)



# ==============================================================================
# 9. Database Connection Pool Metrics (Phase 18)
# ==============================================================================

DB_POOL_SIZE_GAUGE = Gauge(
    "fieldops_db_pool_size",
    "Configured base connection pool size.",
)

DB_POOL_CHECKEDIN_GAUGE = Gauge(
    "fieldops_db_pool_checkedin",
    "Current number of idle connections checked in to the pool.",
)

DB_POOL_CHECKEDOUT_GAUGE = Gauge(
    "fieldops_db_pool_checkedout",
    "Current number of active connections checked out from the pool.",
)

DB_POOL_OVERFLOW_GAUGE = Gauge(
    "fieldops_db_pool_overflow",
    "Current number of overflow connections in use.",
)

# ==============================================================================
# 10. Service Lifecycle Metrics (Phase 24)
# ==============================================================================

REQUESTS_COMPLETED_TOTAL = Counter(
    "fieldops_requests_completed_total",
    "Total completed service requests.",
)

REQUESTS_CANCELLED_TOTAL = Counter(
    "fieldops_requests_cancelled_total",
    "Total cancelled service requests.",
)

RESCHEDULE_REQUESTS_TOTAL = Counter(
    "fieldops_reschedule_requests_total",
    "Total reschedule requests initiated.",
)

RESCHEDULE_SUCCESS_TOTAL = Counter(
    "fieldops_reschedule_success_total",
    "Total approved reschedule requests.",
)

REASSIGNMENTS_TOTAL = Counter(
    "fieldops_reassignments_total",
    "Total technician reassignments performed.",
)

APPOINTMENTS_IN_PROGRESS_GAUGE = Gauge(
    "fieldops_appointments_in_progress",
    "Current number of appointments in progress.",
)


def update_db_pool_metrics() -> None:
    """Collect real-time connection pool statistics from SQLAlchemy engine."""
    try:
        from fieldops.db.session import engine
        pool = engine.pool
        if hasattr(pool, "size"):
            DB_POOL_SIZE_GAUGE.set(pool.size())
        if hasattr(pool, "checkedin"):
            DB_POOL_CHECKEDIN_GAUGE.set(pool.checkedin())
        if hasattr(pool, "checkedout"):
            DB_POOL_CHECKEDOUT_GAUGE.set(pool.checkedout())
        if hasattr(pool, "overflow"):
            DB_POOL_OVERFLOW_GAUGE.set(pool.overflow())
    except Exception:
        pass


def get_metrics_response() -> Response:
    """Generate Prometheus exposition text format response."""
    update_db_pool_metrics()
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


