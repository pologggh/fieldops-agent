# FieldOps Agent Reliability & Consistency Engineering

## 1. Reliability Principles

FieldOps Agent is engineered for mission-critical operations where appointment collisions, dual state mutations, and data loss cannot occur even in the face of worker crashes, API restarts, or network disruptions.

---

## 2. Zero Dual-State Transaction Boundaries

Divergent states (e.g. an appointment scheduled while the ticket is cancelled, or an appointment completed while the ticket remains in review) cause customer confusion and operational gridlock.

To prevent this, status transitions use application domain transactions (`AppointmentService` and `main.py`):

```python
# Atomic completion boundary
with session.begin_nested() if session.in_transaction() else session.begin():
    appointment.status = "completed"
    if appointment.service_request_id:
        sr = service_request_repo.get_by_id(appointment.service_request_id)
        if sr and sr.status != "completed":
            sr.status = "completed"
            audit_log_repo.create(...)
    audit_log_repo.create(...)
    outbox_repo.create(event_type="appointment.completed", ...)
```

---

## 3. Transactional Outbox Pattern & External Integration Decoupling

External communication failures (e.g., Google Calendar rate limits, SendGrid timeouts) **never roll back core appointment bookings**.

```
[ Operator Approval / Customer Confirm ]
                   |
     BEGIN DB Transaction
       1. Insert / Update Appointment (status='scheduled')
       2. Update ServiceRequest (status='scheduled')
       3. Insert AuditLog
       4. Insert OutboxEvent (status='pending')
     COMMIT DB Transaction
                   |
             (Async Worker)
      Celery / Outbox Worker polls OutboxEvent
         |-- Call Google Calendar API -> Transient Failure?
         |     |-- Increment retry count
         |     |-- Exponential backoff
         |     |-- Core Appointment remains SCHEDULED!
         v
      Success -> OutboxEvent marked 'processed'
```

---

## 4. API Restart & Workflow Resumption (HITL)

When an emergency or standard request is paused at a human-in-the-loop (HITL) review stage:
1. The state is durably saved in the persistent store (PostgreSQL / SQLite).
2. If the FastAPI process restarts or crashes, the workflow execution checkpoint and the database `ServiceRequest` records are preserved.
3. When the Operator logs in, requests in `waiting_for_approval`, `ready_for_review`, or `needs_rescheduling` are displayed with refreshed candidate rankings.
4. Operator approval or rejection resumes the workflow or performs atomic state finalization seamlessly.

---

## 5. Concurrency & Double-Action Protection

1. **Double Confirmation Protection**:
   - Customer conversation confirmation requires an `idempotency_key`.
   - The conversation stores `submitted_service_request_id`. Subsequent confirm requests replay the original response idempotently without spawning duplicate tickets.
2. **Double Approval Protection**:
   - Operator approvals verify that the request is in an eligible status (`created`, `received`, `waiting_for_approval`, `ready_for_review`, `needs_rescheduling`).
   - If two operators click approve simultaneously, row-level locks and status checks ensure only one appointment is created; the subsequent call returns HTTP 409 Conflict.
3. **Double Message Send**:
   - Messages support `client_message_id`. Duplicate sends return the existing message without running redundant LLM parsing turns.

---

## 6. Admin Safety Guards

1. **Active Technician Deactivation Guard**:
   - An administrator cannot deactivate a technician who has scheduled future appointments.
   - The system queries `Appointment.status == 'scheduled' AND Appointment.start_time >= now_utc`.
   - If active appointments exist, HTTP 409 Conflict is returned with the count of active appointments.
2. **Last Active Admin Guard**:
   - The system prohibits deactivating or revoking the role of the final active administrator.
