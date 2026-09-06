# FieldOps Cross-Role Authorization Matrix

This document defines the Role-Based Access Control (RBAC) and data isolation boundaries across all four system personas: **Customer**, **Operator**, **Viewer**, and **Admin**.

---

## 1. Persona Definitions & Token Types

| Persona | Token Type (`jwt.type`) | Context Scope | Session Storage Key | Primary Entry Point |
| :--- | :--- | :--- | :--- | :--- |
| **Customer** | `customer` | Tenant boundary: `customer_id == current_customer.id` | `fieldops_customer_token` | `/customer/home` |
| **Operator** | `access` (`role=operator`) | Operations team (Workflows, Dispatch, HITL, Appointments) | `fieldops_auth_token` | `/dashboard` |
| **Viewer** | `access` (`role=viewer`) | Read-only operational inspection | `fieldops_auth_token` | `/dashboard` (Read-only) |
| **Admin** | `access` (`role=admin`) | System governance, policies, users, technicians, audit | `fieldops_auth_token` | `/admin` |

---

## 2. Cross-Resource Permission Matrix

| Resource Domain | Action | Customer | Operator | Viewer | Admin | Enforcement Mechanism |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Conversations** | Create / Send Message | **Allow** (Own) | Deny (403) | Deny (403) | Deny (403) | `get_current_customer` + Anti-IDOR |
| | Confirm Draft | **Allow** (Own) | Deny (403) | Deny (403) | Deny (403) | `get_current_customer` + Anti-IDOR |
| | Read History | **Allow** (Own) | Deny (403) | Deny (403) | Deny (403) | `customer_id == current_customer.id` (404) |
| **Customer Profile** | Read / Update Profile | **Allow** (Own) | Read (Masked) | Read (Masked) | Read (Audit) | Anti-IDOR customer isolation |
| **Service Requests** | Create Request | **Allow** (Own) | **Allow** (Intake) | Deny (403) | Deny (403) | `source="customer_portal"` / Inbound API |
| | Read Detail | **Allow** (Own) | **Allow** (Full) | **Allow** (Full) | **Allow** (Full) | Customer: Anti-IDOR / Internal: RBAC |
| | Supplement Information | **Allow** (Own) | **Allow** | Deny (403) | Deny (403) | Validates `sr.customer_id == customer.id` |
| | Cancel Request | **Allow** (Own) | **Allow** | Deny (403) | **Allow** | State guard + Ownership check |
| | Request Reschedule | **Allow** (Own) | **Allow** | Deny (403) | Deny (403) | Validates `sr.customer_id == customer.id` |
| **Appointments** | Read Appointment | **Allow** (Own) | **Allow** (All) | **Allow** (All) | **Allow** (All) | Customer sanitized view vs Internal view |
| | Cancel Appointment | **Allow** (Own) | **Allow** | Deny (403) | **Allow** | Transitions Appointment & SR atomically |
| | Complete Appointment | Deny (403) | **Allow** | Deny (403) | Deny (403) | Operator production action only |
| **Dispatch & HITL** | View Dispatch Rankings | Deny (403) | **Allow** | **Allow** | **Allow** | Concealed from customer projection |
| | Approve Proposal | Deny (403) | **Allow** | Deny (403) | Deny (403) | `require_operator` RBAC dependency |
| | Reject Proposal | Deny (403) | **Allow** | Deny (403) | Deny (403) | `require_operator` RBAC dependency |
| **Escalations** | List / Acknowledge / Resolve | Deny (403) | **Allow** | Read Only | **Allow** | `require_operator` / `require_admin` |
| **Technicians** | View Public Specialist | Name Only | **Allow** (All) | **Allow** (All) | **Allow** (All) | Customer sees display name only |
| | Create / Update / Deactivate | Deny (403) | Deny (403) | Deny (403) | **Allow** | `get_current_admin` dependency |
| **Policies (Dispatch/SLA)** | View Active & History | Deny (403) | Read Only | Read Only | **Allow** (All) | `get_current_admin` for mutations |
| | Create / Activate / Rollback | Deny (403) | Deny (403) | Deny (403) | **Allow** | `get_current_admin` dependency |
| **Internal Users** | Manage Users & Roles | Deny (403) | Deny (403) | Deny (403) | **Allow** | Last-active-admin protection |
| **Audit Logs** | Read Audit Trails | Own Timeline | Recent Summary | Deny (403) | **Allow** (Full) | Read-only with zero secret disclosure |
| **System Governance** | Health / Telemetry | Deny (403) | Summary | Summary | **Allow** (Full) | Zero credentials or env secrets exposed |

---

## 3. Strict Boundary Rules

1. **Hard Token Boundary**:
   - `InternalTokenBoundaryMiddleware` checks incoming `Authorization` headers. If a JWT carries `type="customer"` on internal endpoints (`/service-requests/*`, `/admin/*`, `/technicians/*`), the request is immediately rejected with `403 Forbidden`.
   - Conversely, operator/admin tokens attempting to query `/customer/*` routes are rejected with `403 Forbidden`.
2. **Anti-Enumeration Anti-IDOR**:
   - Customer endpoints never return `403 Forbidden` on foreign resource lookups (e.g. Customer A requesting Customer B's request `#99`). Instead, queries strictly filter `customer_id == current_customer.id` and return `404 Not Found` to prevent resource ID enumeration attacks.
3. **Role Partitioning**:
   - Operator manages operational lifecycles (HITL approval, conflict resolution, appointment completion).
   - Admin manages governance (users, technicians, weights, SLA thresholds, security audits). Admin does not perform day-to-day work orders.
