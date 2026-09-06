# FieldOps Agent System Architecture (Phase 23)

## 1. Architectural Overview

FieldOps Agent is an autonomous, reliable, human-in-the-loop field service management and scheduling platform. It coordinates three distinct stakeholder experiences (**Customer Portal**, **Operator Dashboard**, and **Admin Console**) around a single canonical data source and business domain model.

```
+-----------------------------------------------------------------------------------+
|                                 CLIENT ROLES                                      |
|                                                                                   |
|  +--------------------+     +---------------------+     +----------------------+  |
|  |  Customer Portal   |     |  Operator Dashboard |     |    Admin Console     |  |
|  |  - Conversational  |     |  - Dispatch Grid    |     |  - User & Role Mgmt  |  |
|  |    Intake (P22)    |     |  - Proposal Review  |     |  - Tech Provisioning |  |
|  |  - Request Status  |     |  - HITL Approval    |     |  - Dispatch Policy   |  |
|  |  - Appointment View|     |  - Escalation Queue |     |  - SLA Policy Mgmt   |  |
|  +---------+----------+     +----------+----------+     +----------+-----------+  |
+------------|---------------------------|---------------------------|--------------+
             |                           |                           |
             | /customer/*               | /service-requests/*       | /admin/*
             v                           v                           v
+-----------------------------------------------------------------------------------+
|                             FASTAPI APPLICATION LAYER                             |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Role-Based Route Guards & Anti-IDOR Tenant Enforcement                      |  |
|  | (Customer vs Internal Operator vs Auditor Viewer vs SuperAdmin)             |  |
|  +-----------------------------------------------------------------------------+  |
|  | Application Services & Domain Handlers                                      |  |
|  | - ConversationService: Multi-turn intent, deterministic validation, draft    |  |
|  | - InboundRequestService: Deduplication, source idempotency, intake           |  |
|  | - AppointmentService: Conflict re-check, zero-dual-state transitions        |  |
|  | - PolicyAttributionEngine: Active policy version snapshotting & deadlines   |  |
|  +-----------------------------------------------------------------------------+  |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        CANONICAL PERSISTENCE LAYER                                |
|                        (Single Source of Truth)                                   |
|                                                                                   |
|  +-------------------+  +-------------------+  +-------------------+              |
|  | Customer & Acct   |  | Conversation & Msg|  | ServiceRequest    |              |
|  | - PII isolated    |  | - State machine   |  | - dispatch_v      |              |
|  | - Password hash   |  | - Client msg idempot| - sla_v, deadline  |              |
|  +---------+---------+  +---------+---------+  +---------+---------+              |
|            |                      |                      |                        |
|            +----------------------+----------------------+                        |
|                                   |                                               |
|                    +--------------+--------------+                                |
|                    v                             v                                |
|          +-------------------+         +-------------------+                      |
|          | Appointment       |         | Transactional     |                      |
|          | - Scheduled / Comp|         | OutboxEvent       |                      |
|          | - Superseded audit|         | - Event decoupling|                      |
|          +---------+---------+         +---------+---------+                      |
|                    |                             |                                |
|                    v                             v                                |
|          +-------------------+         +-------------------+                      |
|          | AuditLog (Readonly|         | Celery Worker     |                      |
|          | - Actor attribution         | - Retries/Backoff |                      |
|          +-------------------+         +-------------------+                      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Canonical Business State vs. Role Projections

A central design principle in Phase 23 is that **all roles view the same business reality through role-specific projections**:

1. **Source of Truth (PostgreSQL / SQLite)**:
   - Contains the canonical business entities: `Customer`, `ServiceRequest`, `Appointment`, `Technician`, `DispatchPolicy`, `SLAPolicy`, `AuditLog`, `OutboxEvent`.
2. **Role-Specific Projections**:
   - **Customer Projection** (`CustomerServiceRequestView`): Strips operational diagnostics, technician scores, and escalation jargon. Maps internal statuses (e.g. `waiting_for_approval`, `needs_rescheduling`, `no_technician_available`) into reassuring, customer-friendly progress updates (e.g. `"Scheduling your visit"`, `"We are reviewing your request"`).
   - **Operator Projection** (`ServiceRequestDetailView`): Exposes full dispatch candidate rankings, multi-factor scoring breakdowns, SLA countdown clocks, and HITL decision actions.
   - **Admin Projection** (`SystemSummaryView`, `AuditLogView`): Summarizes macro system health, open escalations, active policy definitions, worker queues, and tamper-resistant audit logs without revealing PII or operational tokens.

---

## 3. Dynamic Policy Version Attribution

When a new `ServiceRequest` is created:
- The system evaluates the currently active `DispatchPolicy` and `SLAPolicy`.
- It snapshots `dispatch_policy_version = active_dp.version` and `sla_policy_version = active_sla.version`.
- It calculates `sla_deadline = now + active_sla.targets[urgency].resolution_minutes`.
- **Historical Immutability**: If an Admin creates and activates Policy v2, historical requests retain their v1 version numbers and SLA deadlines. New requests automatically bind to v2.

---

## 4. Zero Dual-State Guarantee

To prevent divergent states between linked tickets and appointments:
1. **Appointment Completion**: Marking an appointment `completed` automatically and atomically marks its parent `ServiceRequest` as `completed` in the same database transaction.
2. **Cancellation**: Customer or operator cancellation marks both `Appointment` and `ServiceRequest` as `cancelled` in a single transaction, writing audit logs and queuing an `appointment.cancelled` outbox event.
3. **Reschedule**: When a customer requests reschedule, prior scheduled appointments are marked `cancelled` with reason `"Superseded by reschedule"`. Upon operator approval of the new window, a new active appointment is created, leaving historical appointment audit trails intact.

---

## 5. External Integration Architecture (Phase 25)

External third-party systems are integrated using the **Hexagonal / Adapter Pattern**, strictly decoupled from core application services and domain models.

```
+-----------------------------------------------------------------------------+
|                           DOMAIN / WORKFLOW LAYER                           |
|  (AppointmentService, ServiceLifecycleService, LangGraph, PostgreSQL DB)     |
+-----------------------------------------------------------------------------+
                                       |
                                       v  Transactional Outbox (OutboxEvent)
+-----------------------------------------------------------------------------+
|                             CELERY TASK QUEUE                               |
|        sync_appointment_calendar() / cancel_appointment_calendar_event()    |
+-----------------------------------------------------------------------------+
                                       |
                                       v  CalendarClient Protocol
+-----------------------------------------------------------------------------+
|                     EXTERNAL INTEGRATION BOUNDARY ADAPTER                   |
|                                                                             |
|      +---------------------------------+  +-------------------------------+ |
|      |       FakeCalendarClient        |  |     GoogleCalendarClient      | |
|      |       (Default in Dev/CI)       |  |     (Google Calendar API v3)  | |
|      |  - In-memory event repository   |  |  - Service Account / OAuth2   | |
|      |  - Deterministic fault injection|  |  - Provider-side correlation  | |
|      |  - Zero network dependencies    |  |  - Private extended properties| |
|      +---------------------------------+  +-------------------------------+ |
+-----------------------------------------------------------------------------+
                                       |
                     +-----------------+-----------------+
                     |                                   |
                     v                                   v
          [ In-Memory Store ]                 [ Google Calendar API ]
```

### Key Architectural Guarantees:
1. **Core Business Fact Protection**: A failure in Google Calendar never rolls back or invalidates confirmed PostgreSQL appointments.
2. **Provider-Side Correlation**: Google Calendar events store `extendedProperties.private.fieldops_appointment_id`. Before inserting, the worker checks if an event already exists, preventing duplicate calendar events across Celery retries or post-creation worker crashes.
3. **Idempotent Deletion**: Google Calendar HTTP 404/410 status codes during cancellation are handled as idempotent successes.
4. **Reconciliation Service**: `CalendarReconciliationService` detects and repairs state drift between local `IntegrationRecord`s and Google Calendar.

