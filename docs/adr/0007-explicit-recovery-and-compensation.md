# ADR 0007: Explicit Recovery Paths, Compensation Semantics, and Core Business Fact Priority

## Status
Accepted

## Context
In field service operations, scheduling an appointment involves two distinct realms:
1. **Core Business Fact**: The legal and operational commitment between the service company, the customer, and the assigned technician (stored in our transactional database).
2. **Auxiliary Integrations**: External synchronization services, such as Google Calendar invitations, SMS notifications, and third-party telematics.

External service providers frequently suffer from transient network partitions, quota rate limits (HTTP 429), or third-party outages. Mismanaged distributed state often causes developers to perform cascading distributed rollbacks or allow external failures to abort local database transactions.

## Decision Drivers
1. **Core Business Fact Priority**: An external provider outage (e.g. Google Calendar down) must never cancel or roll back a confirmed, customer-facing field appointment in our database.
2. **Deterministic Fault Isolation**: Failures must be explicitly categorized into transient (retryable) vs permanent (non-retryable) vs invariant violations.
3. **Loop Prevention & Resource Bounding**: Workflows must guarantee termination and prevent infinite retry loops through strict budgeting (`MAX_RETRY_BUDGET = 3`, `MAX_CLARIFICATION_COUNT = 3`, `MAX_RESCHEDULE_COUNT = 3`, `MAX_WORKFLOW_STEPS = 25`).
4. **Structured Compensation Semantics**: When business actions fail or are rejected by human supervisors, compensating actions (releasing schedule locks, staging calendar deletions, notifying operators) must execute cleanly without distributed transaction coordinators.

## Decision
We adopted **Core Business Fact Priority with Transactional Outbox and Explicit Compensation**:

1. **Transactional Outbox for External Integrations**:
   - Appointment creation and scheduling state are committed atomically in PostgreSQL/SQLite.
   - External calendar sync events are inserted into the `outbox_events` table within the same transaction.
   - Asynchronous Celery workers process outbox events independently. If Google Calendar fails, the appointment remains confirmed; the outbox task retries with backoff and marks the `IntegrationRecord` as `failed` for operator reconciliation.

2. **Dedicated Compensation Engine (`CompensationEngine`)**:
   - Located in `src/fieldops/agent/decisions/compensation.py`.
   - Executes non-transactional compensating actions:
     - `RELEASE_LOCK`: Unlocks candidate technician slots.
     - `CANCEL_EXTERNAL_EVENT`: Stages cancellation events for remote calendars.
     - `MARK_INTEGRATION_FAILED`: Marks synchronization records and flags for manual reconciliation.
     - `ALERT_OPERATOR`: Emits high-priority operations queue alerts.

3. **Finite State Machine Invariant Guard (`invariants.py`)**:
   - Maintains an authoritative transition table (`VALID_WORKFLOW_TRANSITIONS`).
   - Rejects illegal state jumps (e.g. attempting to schedule a `completed` or `cancelled` request).
   - Enforces execution step budgets (`step_count <= 25`), raising `WorkflowInvariantError` before any runaway execution can occur.

## Consequences
### Positive:
- **Resilience to Third-Party Downtime**: Field appointments remain 100% stable during cloud vendor outages.
- **Zero Orphaned State**: Transient failures retry predictably; permanent failures escalate immediately without wasting retries.
- **Provable Termination**: Loop counters guarantee every workflow run halts within 25 steps.
- **Safe Reconciliation**: Discrepancies between local database state and external providers are easily healed via `CalendarReconciliationService`.

### Negative / Trade-offs:
- External calendar synchronization is eventually consistent rather than immediately synchronous. (This is standard best practice for resilient distributed systems).
