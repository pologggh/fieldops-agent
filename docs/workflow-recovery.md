# FieldOps Workflow Recovery & Compensation Semantics

This document defines the recovery semantics, fault isolation boundaries, retry budgeting, and compensation mechanics introduced in Phase 28 for the FieldOps Agent platform.

---

## 1. Architectural Philosophy: Core Business Fact Priority

In distributed field service automation, external dependencies (Google Calendar API, SendGrid, Twilio, external routing engines) exhibit higher failure rates and network instability than our transactional database (PostgreSQL/SQLite).

**The Golden Invariant**:
> External integration outages, rate limits, network partitions, or third-party 5xx errors **must never roll back or jeopardize confirmed internal appointments or service requests**.

```
+-----------------------------------------------------------------------------+
|                            DATABASE TRANSACTION                             |
|                                                                             |
|  1. ServiceRequest updated to 'scheduled'                                   |
|  2. Appointment record created with technician & slot                       |
|  3. Transactional Outbox event staged ('appointment.created')               |
|  4. AuditLog recorded with actor attribution                                |
|                                                                             |
|                       [ COMMIT TRANSACTION SUCCESS ]                        |
+-----------------------------------------------------------------------------+
                                      |
                     (Asynchronous Outbox Dispatch via Celery)
                                      |
                                      v
                      +-------------------------------+
                      | External Sync: Google Calendar|
                      +-------------------------------+
                                      |
                         +------------+------------+
                         |                         |
                      Success                   Failure
                         |                         |
                         v                         v
               [IntegrationRecord:        [Outbox retry + Celery Backoff]
                    'synced']                      |
                                           Budget Exhaustion:
                                                   |
                                                   v
                                        [Compensation Action:
                                         Mark 'failed', Alert Ops,
                                         Retain Postgres Appointment!]
```

---

## 2. Compensation vs Database Rollback

Traditional distributed systems often misuse two-phase commits or attempt catastrophic database rollbacks when auxiliary services fail. FieldOps establishes an explicit semantic boundary:

| Failure Type | Example | Recovery / Compensation Mechanism |
|---|---|---|
| **Intra-Transaction Failure** | Unique slot constraint violated, customer foreign key missing, DB disconnect during insert | **Database Transaction Rollback**: Handled cleanly by SQLAlchemy context manager. Checkpoint state captures error; no orphaned rows created. |
| **External Integration Failure** | Google Calendar 429 rate limit, 503 service unavailable, invalid OAuth token | **Transactional Outbox Retry + Compensation**: Outbox event retried up to 5 times with exponential backoff. If exhausted, status marked `failed`, alert queued for ops reconciliation. Appointment in DB remains valid. |
| **Human Operational Rejection** | Operator rejects automated appointment proposal | **Compensation Action (`RELEASE_LOCK`)**: Staged schedule slots released, ServiceRequest transitioned to `rejected`, reason logged in `AuditLog`. |
| **Customer / System Reschedule** | Customer changes time, or weather disruption forces re-dispatch | **Compensation Action (`CANCEL_AND_RESCHEDULE`)**: Existing appointment marked `cancelled` with reason `"Superseded by reschedule"`, external calendar event cancelled via Outbox, fresh appointment scheduled. |

---

## 3. Retry Budget & Loop Guards

Uncontrolled loops in agentic workflows lead to cascading latency, cost overruns, and deadlocks. Phase 28 introduces four strict operational loop counters:

```python
# Defined in fieldops.agent.invariants
MAX_WORKFLOW_STEPS = 25
MAX_CLARIFICATION_COUNT = 3
MAX_RESCHEDULE_COUNT = 3
MAX_RETRY_BUDGET = 3
```

### Counter Semantics & Guardrails

1. **`step_count` (Bound: 25 steps)**:
   - Tracks total graph node executions across subgraphs.
   - Enforced by `validate_workflow_invariants(state)`.
   - Exceeding 25 steps raises `WorkflowInvariantError`, terminating graph execution and preventing infinite cycling.

2. **`clarification_count` (Bound: 3 turns)**:
   - Tracks how many times the workflow prompts the user for missing fields (`service_type`, `location`, `urgency`).
   - If `clarification_count >= 3`, `evaluate_request_intake_decision` switches action from `ASK_FOR_INFORMATION` to `ESCALATE` with `ReasonCode.CLARIFICATION_LIMIT_EXCEEDED`, assigning the request to a human operator.

3. **`reschedule_count` (Bound: 3 attempts)**:
   - Tracks sequential rescheduling cycles when technician slots conflict.
   - If `reschedule_count >= 3`, `reschedule_subgraph` escalates to `OPERATOR` with `ReasonCode.RESCHEDULE_LIMIT_EXCEEDED`.

4. **`retry_count` & `retry_budget` (Bound: 3 retries)**:
   - Tracks transient failure retries (e.g. LLM timeout, transient network error).
   - Once `retry_count >= retry_budget`, `evaluate_recovery_decision` transitions action to `ESCALATE` with `ReasonCode.RETRY_BUDGET_EXHAUSTED`.

---

## 4. Compensation Engine API (`CompensationEngine`)

Located in `src/fieldops/agent/decisions/compensation.py`, `CompensationEngine` provides deterministic execution of compensation actions:

```python
from fieldops.agent.decisions.compensation import CompensationAction, CompensationEngine

# Example: Compensate for failed external sync
result = CompensationEngine.execute(
    action=CompensationAction.ALERT_OPERATOR,
    target_entity="appointment",
    entity_id=101,
    details={"provider": "google_calendar", "error": "QuotaExceeded"},
)
assert result.success is True
```

### Supported Compensation Actions
- `RELEASE_LOCK`: Free soft reservations or candidate holds.
- `CANCEL_EXTERNAL_EVENT`: Stage an outbox deletion event for third-party calendar providers.
- `MARK_INTEGRATION_FAILED`: Update `IntegrationRecord.status` to `failed` and record error diagnostic payload.
- `ALERT_OPERATOR`: Dispatch a high-priority operational alert to the dashboard and notification bus.
- `ROLLBACK_LOCAL_DRAFT`: Cleanly remove uncommitted in-memory or session draft records.
