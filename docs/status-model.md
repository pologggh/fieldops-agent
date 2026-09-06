# FieldOps Canonical Status & Lifecycle Model

This document establishes the single source of truth for all status models and cross-role state projections across the FieldOps Agent platform.

---

## 1. Status Overview by Domain

| Domain | Entity / Layer | Allowed Status Values | Description |
| :--- | :--- | :--- | :--- |
| **Conversation** | `conversations.status` | `active`<br>`awaiting_confirmation`<br>`submitted`<br>`cancelled` | Lifecycle of the customer conversational intake session. Transitions to `submitted` only upon explicit user confirmation. |
| **Workflow** | LangGraph State `workflow_status` | `parsed`<br>`needs_information`<br>`matched`<br>`no_technician_available`<br>`ready_for_scheduling`<br>`waiting_for_approval`<br>`scheduled`<br>`rejected`<br>`conflict`<br>`completed` | Execution state of the internal LangGraph workflow engine. |
| **ServiceRequest** | `service_requests.status` | `created`<br>`needs_information`<br>`waiting_for_approval`<br>`ready_for_review`<br>`scheduled`<br>`in_progress`<br>`completed`<br>`cancelled`<br>`rejected`<br>`conflict`<br>`needs_rescheduling`<br>`reschedule_requested`<br>`no_technician_available` | Canonical business status of the service ticket in PostgreSQL/SQLite. |
| **Appointment** | `appointments.status` | `scheduled`<br>`in_progress`<br>`completed`<br>`cancelled`<br>`needs_rescheduling` | Operational calendar booking record for an assigned technician. |
| **Escalation** | Operational Queue | `open`<br>`acknowledged`<br>`resolved` | Operator/Admin attention flag for SLA at-risk/breached requests, emergency tickets, or unmatchable trades. |
| **Integration** | `integration_records.status` | `pending`<br>`processing`<br>`synced`<br>`failed`<br>`cancelled` | External calendar (Google/Outlook) and notification (SendGrid/SMS) synchronization status. |
| **Customer Projection** | `CustomerServiceRequestView.customer_status` | *See Customer Status Projection below* | Sanitized, customer-friendly status generated deterministically by the backend API. |

---

## 2. Canonical Status Mapping Table

| ServiceRequest Status (`sr.status`) | Appointment Status (`appt.status`) | Customer-Facing Status (`customer_status`) | Operator Dashboard Status | Admin Console Telemetry |
| :--- | :--- | :--- | :--- | :--- |
| `received` / `created` | *None* | **Request received** | `created` (Intake queue) | `open_service_requests` +1 |
| `needs_information` | *None* | **More information needed** | `needs_information` (Flagged) | `open_service_requests` +1 |
| `validated` / `matched` | *None* | **Finding a technician** | `matched` / `ready_for_scheduling` | `open_service_requests` +1 |
| `waiting_for_approval` / `ready_for_review` | *None* | **Scheduling your visit** | `waiting_for_approval` (Review queue) | `open_service_requests` +1 |
| `scheduled` | `scheduled` | **Appointment scheduled** | `scheduled` (Confirmed calendar) | `open_service_requests` +1 |
| `in_progress` | `in_progress` | **Service in progress** | `in_progress` (On-site) | `open_service_requests` +1 |
| `completed` | `completed` | **Service completed** | `completed` (Historical log) | Archived |
| `cancelled` | `cancelled` | **Cancelled** | `cancelled` (Cancelled log) | Archived |
| `rejected` | *None* | **We are reviewing alternative scheduling options.** | `rejected` (Operator rejected) | `open_escalations_count` +1 |
| `conflict` / `needs_rescheduling` | `needs_rescheduling` | **We are reviewing your request** | `needs_rescheduling` (Conflict flag) | `open_escalations_count` +1 |
| `reschedule_requested` | `needs_rescheduling` | **Reschedule in progress** | `needs_rescheduling` (Review queue) | `open_escalations_count` +1 |
| `no_technician` / `no_technician_available` | *None* | **We are reviewing your request** | `no_technician_available` (Escalation) | `open_escalations_count` +1 |

---

## 3. Strict State Invariants

1. **Zero Dual States**:
   - It is impossible for `ServiceRequest` to be `cancelled` while `Appointment` remains `scheduled`. Both are transitioned atomically in `cancel_appointment()`.
   - It is impossible for `Appointment` to be `completed` while `ServiceRequest` remains `scheduled`. Both are transitioned atomically in `complete_appointment()`.
2. **Deterministic Customer Projection**:
   - The customer UI **never** infers status via client-side `if/else` ladders. The backend `build_customer_sr_view()` deterministically sets `customer_status`.
   - Internal technical terms (e.g. `waiting_for_approval`, `dispatch.ranked`, `worker.retry`) are strictly purged from customer-facing views.
3. **Reschedule Historical Preservation**:
   - Approving a reschedule cancels the prior appointment with reason `"Superseded by reschedule"` and creates a new appointment record. Historical booking data is never overwritten.
4. **Policy Attribution Pinning**:
   - `dispatch_policy_version` and `sla_policy_version` are recorded at creation time on `ServiceRequest`.
   - Activating a new policy version only affects subsequent requests. Historical SLA deadlines remain immutable.
