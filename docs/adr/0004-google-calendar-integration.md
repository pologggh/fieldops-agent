# ADR 0004: Google Calendar as Initial External Integration Provider

## Status
Accepted

## Context
FieldOps Agent manages field service operations, scheduling, dispatching, and appointment lifecycle tracking. To coordinate with customer service workflows and external calendar systems, field operations appointments must synchronize with external calendar providers.

Prior to Phase 25, calendar operations were handled exclusively by `FakeCalendarClient` in memory. We needed to integrate our first real third-party external service without violating the system's core architecture.

## Decision Drivers
1. **Domain & Workflow Isolation**: Core appointment scheduling, dispatch algorithms, LangGraph workflows, and PostgreSQL business models must remain completely decoupled from third-party vendor SDKs.
2. **PostgreSQL Business Fact Priority**: Third-party calendar outages (rate limits, 5xx server errors, network partitions) must never roll back or jeopardize confirmed PostgreSQL appointments.
3. **Provider-Side Idempotency & Crash Recovery**: Celery worker retries or crashes occurring between provider event creation and database commit must not create duplicate calendar events.
4. **Credential Security**: Credentials, API tokens, and service account keys must never be committed to Git, baked into Docker images, or exposed to frontend clients.
5. **Testability & Determinism**: Development and CI test suites must continue running fast, hermetic, and offline without requiring active external Google accounts.

## Decision
We implemented `GoogleCalendarClient` as an adapter implementing the `CalendarClient` protocol alongside `FakeCalendarClient`:

1. **Adapter Pattern (Hexagonal Architecture)**:
   - All external interaction is encapsulated within `src/fieldops/integrations/calendar/google.py`.
   - Domain layers and Celery tasks only communicate via the abstract `CalendarClient` contract and pure Python DTOs (`CalendarEventCreate`, `CalendarEventResult`).
   - `googleapiclient` is never imported outside the integration adapter.

2. **Authentication Strategy**:
   - **Google Service Account** is the primary recommended server-to-server mechanism for headless Celery workers, authenticated via `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_CREDENTIALS_JSON`. The service account is granted access by sharing the dedicated target calendar (`GOOGLE_CALENDAR_ID`).
   - **OAuth2 Refresh Token** is supported as an alternative via `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REFRESH_TOKEN`.
   - Application Default Credentials (ADC) is supported as a fallback for GCP environments.

3. **Provider-Side Correlation & Idempotency**:
   - Every Google Calendar event includes private metadata:
     `extendedProperties.private.fieldops_appointment_id = str(appointment.id)`
   - Prior to calling `events.insert()`, `GoogleCalendarClient` executes an `events.list()` filtered by `privateExtendedProperty=fieldops_appointment_id={id}`.
   - If an active event already exists, the adapter returns the existing ID without duplicate creation, guaranteeing idempotent execution across Celery retries and post-creation worker crashes.

4. **Lifecycle Synchronization Semantics**:
   - **Creation**: Syncs new Google Calendar event.
   - **Cancellation**: Idempotently deletes Google Calendar event, safely handling HTTP 404/410 as successful deletion.
   - **Reschedule**: In alignment with Phase 24 lifecycle history preservation, cancels the legacy appointment's calendar event and creates a fresh event for the replacement appointment.

5. **Retention of `FakeCalendarClient`**:
   - `FakeCalendarClient` remains the default (`CALENDAR_PROVIDER=fake`) for local development, unit tests, and CI pipelines.
   - `GoogleCalendarClient` is explicitly enabled via `CALENDAR_PROVIDER=google`.
   - In production (`APP_ENV=production`), `FakeCalendarClient` is prohibited unless `ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION=true`.

6. **Lightweight Reconciliation**:
   - `CalendarReconciliationService` identifies discrepancies between PostgreSQL `IntegrationRecord` and Google Calendar event states (`unsynced_local`, `missing_remote`, `remote_cancelled`, `cancelled_appointment_active_remote`) and provides safe self-healing actions.

## Consequences
### Positive:
- Domain and workflow code remains 100% vendor-agnostic.
- System is resilient to external provider downtime: calendar failures are quarantined in Celery tasks and `IntegrationRecord`s without affecting transactional database consistency.
- Duplicate calendar events are prevented even under arbitrary worker crashes.
- Fast, hermetic CI runs without external network dependencies or credentials.

### Negative / Trade-offs:
- Private extended property lookup adds one additional `events.list()` API call prior to `events.insert()`. (Mitigated: API quota usage is minimal compared to the business cost of duplicate calendar invitations).
- Google Calendar integration currently creates events with `sendUpdates="none"` to prevent unintended external emails during staging and testing.
