# FieldOps Agent - Final Production Risk Register (Phase 26)

This document provides a comprehensive risk assessment for the FieldOps Agent system across architecture, third-party dependencies, operational boundaries, and security.

---

## 1. Risk Matrix Overview

| Risk ID | Category | Risk Description | Severity | Likelihood | Residual Risk | Status |
|---|---|---|---|---|---|---|
| **RISK-01** | Architecture | Single-Region PostgreSQL Database (SPOF) | High | Medium | Medium | Mitigated with Outbox & Retry |
| **RISK-02** | External Dependency | LLM Provider Outage / Latency Degradation | High | Medium | Low | Mitigated with Fake Fallback & HTTP 503 |
| **RISK-03** | External Dependency | Google Calendar API Quota & Rate Throttling | Medium | High | Low | Mitigated with Celery Backoff & Sync Daemon |
| **RISK-04** | Operational | Lack of Native Production SMS/Email Adapter | Medium | Low | Medium | Outbox Ready for Production Binding |
| **RISK-05** | Multi-Tenancy | Single-Tenant Database Schema Partitioning | Medium | Low | Low | Suitable for dedicated enterprise instances |
| **RISK-06** | Concurrency | High-Frequency Appointment Race at Peak Hours | High | Low | Low | Mitigated with DB Transactions & Strict Locks |

---

## 2. Detailed Risk Profiles & Mitigations

### RISK-01: Single-Region PostgreSQL Database (SPOF)
- **Description**: The database is hosted in a single region without synchronous read-replicas or automatic multi-region failover. An outage in the primary availability zone will temporarily disrupt order intake and scheduling.
- **Impact**: All write transactions (`ServiceRequest`, `Appointment`, `AuditLog`) halt during database downtime.
- **Mitigation Implemented**:
  - Stateless API nodes fail fast and return structured HTTP 503 errors.
  - Transactional Outbox pattern guarantees that once DB recovers, no asynchronous notifications or external synchronization events are lost.
- **Recommended Production Action**:
  - Deploy PostgreSQL on AWS RDS Multi-AZ or Google Cloud SQL HA with automated standby failover.

---

### RISK-02: LLM External API Dependency & Latency Spikes
- **Description**: Conversational intake and structured parsing depend on upstream LLM API responsiveness. Vendor latency spikes or HTTP 429/500 errors could delay request processing.
- **Impact**: Increased turn latency in Customer Assistant dialogue; potential intake timeouts.
- **Mitigation Implemented**:
  - Exponential backoff retry with jitter (`OpenAIClient.parse_structured`).
  - Timeout enforcement (`LLMTimeoutError`) mapping cleanly to HTTP 503 with retry-after hints.
  - Offline deterministic fallback (`LLM_PROVIDER="fake"`) ensuring 100% availability during network disconnection or integration testing.
  - Conversational Agent boundary rejects prompt injection without delegating state mutation to the model.
- **Recommended Production Action**:
  - Establish multi-provider fallback routing (e.g. Gemini 1.5 Flash -> OpenAI GPT-4o-mini).

---

### RISK-03: Google Calendar API Rate Limits & Quotas
- **Description**: Google Calendar API enforces per-project queries per minute and per-user limits. High-frequency dispatch cycles could trigger HTTP 403 `rateLimitExceeded`.
- **Impact**: Delay in updating technician external calendars.
- **Mitigation Implemented**:
  - Asynchronous Celery task processing (`sync_appointment_calendar`) with exponential backoff (`TransientIntegrationError`).
  - Idempotent private extended properties prevent event duplication upon retry.
  - `CalendarReconciliationService` audits and repairs drift without continuous webhook polling.
- **Recommended Production Action**:
  - Request quota increase in Google Cloud Console for enterprise production volumes; batch sync operations where possible.

---

### RISK-04: Outbox Ready but Native SMS/Email Provider Unbound
- **Description**: The system reliably queues `appointment.created`, `appointment.reminder`, and `appointment.completed` into the `outbox_events` table. However, real SendGrid/Twilio API keys are not bound in this phase.
- **Impact**: Customers do not receive real SMS notifications unless an adapter is wired to the Celery outbox tasks.
- **Mitigation Implemented**:
  - Zero-loss Transactional Outbox ensures all notification jobs are persisted in the database.
  - Celery eager and Celery background workers process jobs reliably.
- **Recommended Production Action**:
  - Implement Twilio SMS adapter and SendGrid Email adapter inheriting from the integration interface.

---

### RISK-05: Multi-Tenancy Database Partitioning
- **Description**: The current schema supports Customer accounts and Internal Operators within a single shared schema. It does not enforce schema-per-tenant or row-level tenant key partitioning.
- **Impact**: Not suitable for public multi-tenant SaaS without tenant isolation layer.
- **Mitigation Implemented**:
  - Strict Anti-IDOR ownership queries (`customer_id == current_customer.id`) prevent cross-account data leakage.
  - Admin and Operator RBAC prevents unauthorized cross-role access.
- **Recommended Production Action**:
  - Add `tenant_id` foreign keys and PostgreSQL Row-Level Security (RLS) policies for multi-tenant SaaS deployments.

---

### RISK-06: Concurrency Race Conditions on Appointment Booking
- **Description**: Multiple customers or operators attempting to book the same technician time slot simultaneously could result in double-booking.
- **Impact**: Technician double-booked for the same window.
- **Mitigation Implemented**:
  - In-database conflict checking with transaction isolation (`has_time_conflict` formula: `existing_start < slot_end AND existing_end > slot_start`).
  - Double-approval idempotent safeguards return 409 Conflict for concurrent requests.
  - Concurrency stress tests verified zero double-booking across 10 concurrent requests.
