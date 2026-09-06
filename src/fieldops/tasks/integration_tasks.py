"""Celery tasks for third-party external integrations (Calendar & Email)."""

from datetime import datetime, timezone
import logging
import random
from typing import Any

from fieldops.core.config import settings
from fieldops.db.session import SessionLocal
from fieldops.integrations import (
    CalendarEventCreate,
    PermanentIntegrationError,
    TransientIntegrationError,
    get_calendar_client,
    get_email_client,
)
from fieldops.integrations.email.renderer import render_appointment_confirmation
from fieldops.observability.metrics import (
    CALENDAR_SYNC_TOTAL,
    EMAIL_NOTIFICATIONS_TOTAL,
    INTEGRATION_DURATION_SECONDS,
    INTEGRATION_FAILURES_TOTAL,
    INTEGRATION_OPERATIONS_TOTAL,
)
from fieldops.observability.tracing import trace_integration_operation
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.customer_repository import CustomerRepository
from fieldops.repositories.integration_repository import IntegrationRepository
from fieldops.repositories.notification_job_repository import (
    NotificationJobRepository,
)
from fieldops.repositories.service_request_repository import (
    ServiceRequestRepository,
)
from fieldops.repositories.technician_repository import TechnicianRepository
from fieldops.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_appointment_calendar(self, appointment_id: int) -> dict[str, Any]:
    """Synchronize an appointment with an external calendar provider.

    Guarantees:
    1. Idempotency: IntegrationRecord and provider-side deduplication.
    2. Fresh DB Read: Checks authoritative Appointment status.
    3. Status Guard: Skips creation if appointment was cancelled before execution.
    4. Safe Retry: Retries transient errors up to 3 times; permanent errors fail immediately.
    """
    task_id = self.request.id or "direct_exec"
    attempt = self.request.retries + 1
    provider_name = f"{settings.CALENDAR_PROVIDER}_calendar"

    with SessionLocal() as session:
        appt_repo = AppointmentRepository(session)
        sr_repo = ServiceRequestRepository(session)
        tech_repo = TechnicianRepository(session)
        integration_repo = IntegrationRepository(session)
        audit_repo = AuditLogRepository(session)

        # 1. Authoritative DB Read
        appointment = appt_repo.get_by_id(appointment_id)
        if not appointment:
            logger.error("sync_appointment_calendar: Appointment %s not found", appointment_id)
            return {"status": "failed", "error": "appointment_not_found"}

        # 2. Status Guard
        if appointment.status == "cancelled":
            logger.info("sync_appointment_calendar: Appointment %s is cancelled. Skipping calendar sync.", appointment_id)
            rec = integration_repo.get_by_provider_resource(provider_name, "appointment", appointment_id)
            if rec:
                rec.status = "cancelled"
                session.commit()
            return {"status": "skipped", "reason": "appointment_cancelled"}

        service_request = sr_repo.get_by_id(appointment.service_request_id)
        technician = tech_repo.get_by_id(appointment.technician_id)
        location = service_request.location if service_request else "Customer Location"
        service_type = service_request.service_type if service_request else "Service"

        # 3. Idempotency & Concurrency Guard via IntegrationRecord
        record, created = integration_repo.get_or_create_for_update(
            provider=provider_name,
            resource_type="appointment",
            local_resource_id=appointment_id,
            default_status="processing",
        )

        if not created and record.status == "synced":
            logger.info(
                "sync_appointment_calendar: Idempotency hit. Appointment %s already synced as %s",
                appointment_id,
                record.external_resource_id,
            )
            return {
                "status": "already_synced",
                "external_event_id": record.external_resource_id,
                "appointment_id": appointment_id,
            }

        if not created and record.status == "processing":
            now_utc = datetime.now(timezone.utc)
            updated_at = record.updated_at
            if updated_at and updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if updated_at and (now_utc - updated_at).total_seconds() > 180:
                logger.warning(
                    "sync_appointment_calendar: Reclaiming stale processing record %s for appt %s",
                    record.id,
                    appointment_id,
                )

        record.status = "processing"
        record.attempt_count = attempt
        session.flush()
        session.commit()

        # 4. Audit Log: sync started
        audit_repo.create(
            entity_type="appointment",
            entity_id=str(appointment_id),
            action="calendar.sync_started",
            details={"provider": provider_name, "attempt": attempt},
        )
        session.commit()

        # 5. External Provider Execution
        try:
            with trace_integration_operation(
                provider=provider_name,
                operation="calendar.sync",
                local_resource_id=appointment_id,
                retry_count=self.request.retries,
            ):
                client = get_calendar_client()
                event_dto = CalendarEventCreate(
                    appointment_id=appointment.id,
                    title=f"FieldOps Appointment #{appointment.id} - {service_type}",
                    start_time=appointment.start_time,
                    end_time=appointment.end_time,
                    location=location,
                    description=f"Assigned Tech: {technician.name if technician else 'Staff'}",
                )
                res = client.create_event(event_dto)

            # 6. Mark Synced in DB
            integration_repo.mark_synced(record.id, res.external_event_id)
            audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="calendar.synced",
                details={"external_event_id": res.external_event_id, "provider": res.provider},
            )
            session.commit()

            INTEGRATION_OPERATIONS_TOTAL.labels(provider=provider_name, operation="calendar.sync", result="success").inc()
            CALENDAR_SYNC_TOTAL.labels(provider=provider_name, status="synced").inc()

            return {
                "status": "synced",
                "appointment_id": appointment_id,
                "external_event_id": res.external_event_id,
                "provider": res.provider,
            }

        except TransientIntegrationError as exc:
            logger.warning("Transient error during calendar sync for appt %s: %s", appointment_id, exc)
            integration_repo.mark_failed(record.id, str(exc))
            audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="calendar.sync_failed",
                details={"error": str(exc), "retryable": True, "attempt": attempt},
            )
            session.commit()

            INTEGRATION_FAILURES_TOTAL.labels(provider=provider_name, operation="calendar.sync").inc()

            if self.request.retries >= self.max_retries:
                logger.error("Max retries exceeded for calendar sync on appt %s", appointment_id)
                CALENDAR_SYNC_TOTAL.labels(provider=provider_name, status="failed").inc()
                INTEGRATION_OPERATIONS_TOTAL.labels(provider=provider_name, operation="calendar.sync", result="failed").inc()
                return {"status": "failed", "error": "max_retries_exceeded"}

            delay = 0 if getattr(self.request, "is_eager", False) else int(
                min(60 * (2 ** self.request.retries), 300) + random.uniform(1, 5)
            )
            raise self.retry(exc=exc, countdown=delay)

        except (PermanentIntegrationError, Exception) as exc:
            logger.error("Permanent failure during calendar sync for appt %s: %s", appointment_id, exc)
            integration_repo.mark_failed(record.id, str(exc))
            audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="calendar.sync_failed",
                details={"error": str(exc), "retryable": False, "attempt": attempt},
            )
            session.commit()

            INTEGRATION_FAILURES_TOTAL.labels(provider=provider_name, operation="calendar.sync").inc()
            CALENDAR_SYNC_TOTAL.labels(provider=provider_name, status="failed").inc()
            INTEGRATION_OPERATIONS_TOTAL.labels(provider=provider_name, operation="calendar.sync", result="failed").inc()

            return {"status": "failed", "error": str(exc)}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def cancel_appointment_calendar_event(self, appointment_id: int) -> dict[str, Any]:
    """Cancel an external calendar event when an appointment is cancelled."""
    provider_name = f"{settings.CALENDAR_PROVIDER}_calendar"

    with SessionLocal() as session:
        integration_repo = IntegrationRepository(session)
        audit_repo = AuditLogRepository(session)

        record = integration_repo.get_by_provider_resource(provider_name, "appointment", appointment_id)
        if not record or not record.external_resource_id:
            logger.info("cancel_appointment_calendar_event: No active external event for appt %s", appointment_id)
            return {"status": "not_synced", "appointment_id": appointment_id}

        try:
            with trace_integration_operation(
                provider=provider_name,
                operation="calendar.cancel",
                local_resource_id=appointment_id,
            ):
                client = get_calendar_client()
                client.cancel_event(record.external_resource_id)

            integration_repo.mark_cancelled(record.id)
            audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="calendar.cancelled",
                details={"external_event_id": record.external_resource_id, "provider": provider_name},
            )
            session.commit()

            CALENDAR_SYNC_TOTAL.labels(provider=provider_name, status="cancelled").inc()
            INTEGRATION_OPERATIONS_TOTAL.labels(provider=provider_name, operation="calendar.cancel", result="success").inc()

            return {"status": "cancelled", "appointment_id": appointment_id, "external_event_id": record.external_resource_id}

        except Exception as exc:
            logger.error("Error cancelling calendar event for appt %s: %s", appointment_id, exc)
            return {"status": "failed", "error": str(exc)}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_appointment_confirmation(self, appointment_id: int) -> dict[str, Any]:
    """Send confirmation email to customer after appointment booking.

    Guarantees:
    1. Recipient Security: Recipient is strictly derived from PostgreSQL Customer.email.
    2. Idempotency: NotificationJob guard prevents duplicate dispatch.
    3. Fresh Data: Uses database models to render template.
    4. Safe Retry: Transient errors retried; permanent errors fail without loop.
    """
    task_id = self.request.id or "direct_exec"
    attempt = self.request.retries + 1
    provider_name = f"{settings.EMAIL_PROVIDER}_email"

    with SessionLocal() as session:
        appt_repo = AppointmentRepository(session)
        sr_repo = ServiceRequestRepository(session)
        cust_repo = CustomerRepository(session)
        tech_repo = TechnicianRepository(session)
        notif_repo = NotificationJobRepository(session)
        audit_repo = AuditLogRepository(session)

        # 1. Authoritative DB Read
        appointment = appt_repo.get_by_id(appointment_id)
        if not appointment:
            return {"status": "failed", "error": "appointment_not_found"}

        if appointment.status == "cancelled":
            logger.info("send_appointment_confirmation: Appointment %s is cancelled. Skipping.", appointment_id)
            return {"status": "skipped", "reason": "appointment_cancelled"}

        service_request = sr_repo.get_by_id(appointment.service_request_id)
        if not service_request:
            return {"status": "failed", "error": "service_request_not_found"}

        # 2. Recipient Security: strictly from database Customer.email
        customer = cust_repo.get_by_id(service_request.customer_id)
        if not customer or not customer.email or "@" not in customer.email:
            logger.error("send_appointment_confirmation: Invalid customer email for appt %s", appointment_id)
            return {"status": "failed", "error": "invalid_customer_email"}

        technician = tech_repo.get_by_id(appointment.technician_id)
        if not technician:
            return {"status": "failed", "error": "technician_not_found"}

        # 3. Idempotency Check on NotificationJob
        norm_created_at = appointment.created_at
        existing_job = notif_repo.get_by_appointment_job_schedule(
            appointment_id=appointment_id,
            job_type="appointment_confirmation",
            scheduled_for=norm_created_at,
        )

        if existing_job:
            if existing_job.status == "completed":
                logger.info("send_appointment_confirmation: Idempotency hit. Job already completed.")
                return {"status": "already_completed", "job_id": existing_job.id, "provider_message_id": existing_job.provider_message_id}
            job = existing_job
            job.status = "processing"
            job.attempt_count = attempt
            session.flush()
            session.commit()
        else:
            job, _ = notif_repo.get_or_create(
                appointment_id=appointment_id,
                job_type="appointment_confirmation",
                scheduled_for=norm_created_at,
                status="processing",
            )
            job.attempt_count = attempt
            session.flush()
            session.commit()

        job_id = job.id

        # 4. Render Email Template
        subject, body = render_appointment_confirmation(
            customer=customer,
            appointment=appointment,
            service_request=service_request,
            technician=technician,
        )

        # 5. Audit Log: send started
        audit_repo.create(
            entity_type="appointment",
            entity_id=str(appointment_id),
            action="email.send_started",
            details={"provider": provider_name, "job_id": job_id, "attempt": attempt},
        )
        session.commit()

        # 6. External Email Dispatch
        try:
            with trace_integration_operation(
                provider=provider_name,
                operation="email.send",
                local_resource_id=appointment_id,
                retry_count=self.request.retries,
            ):
                client = get_email_client()
                result = client.send_email(
                    recipient=customer.email,
                    subject=subject,
                    body=body,
                    metadata={"notification_job_id": job_id, "appointment_id": appointment.id},
                )

            # 7. Mark Completed in Database
            notif_repo.mark_completed(
                job_id=job_id,
                provider=result.provider,
                provider_message_id=result.provider_message_id,
                sent_at=datetime.now(timezone.utc),
            )
            audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="email.sent",
                details={"provider": result.provider, "provider_message_id": result.provider_message_id, "job_id": job_id},
            )
            session.commit()

            EMAIL_NOTIFICATIONS_TOTAL.labels(provider=provider_name, status="sent").inc()
            INTEGRATION_OPERATIONS_TOTAL.labels(provider=provider_name, operation="email.send", result="success").inc()

            return {
                "status": "completed",
                "job_id": job_id,
                "appointment_id": appointment_id,
                "provider_message_id": result.provider_message_id,
                "provider": result.provider,
            }

        except TransientIntegrationError as exc:
            logger.warning("Transient error sending confirmation for appt %s: %s", appointment_id, exc)
            notif_repo.mark_failed(job_id, str(exc))
            audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="email.failed",
                details={"error": str(exc), "retryable": True, "attempt": attempt},
            )
            session.commit()

            INTEGRATION_FAILURES_TOTAL.labels(provider=provider_name, operation="email.send").inc()

            if self.request.retries >= self.max_retries:
                EMAIL_NOTIFICATIONS_TOTAL.labels(provider=provider_name, status="failed").inc()
                INTEGRATION_OPERATIONS_TOTAL.labels(provider=provider_name, operation="email.send", result="failed").inc()
                return {"status": "failed", "job_id": job_id, "error": "max_retries_exceeded"}

            delay = 0 if getattr(self.request, "is_eager", False) else int(
                min(60 * (2 ** self.request.retries), 300) + random.uniform(1, 5)
            )
            raise self.retry(exc=exc, countdown=delay)

        except (PermanentIntegrationError, Exception) as exc:
            logger.error("Permanent failure sending confirmation for appt %s: %s", appointment_id, exc)
            notif_repo.mark_failed(job_id, str(exc))
            audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="email.failed",
                details={"error": str(exc), "retryable": False, "attempt": attempt},
            )
            session.commit()

            INTEGRATION_FAILURES_TOTAL.labels(provider=provider_name, operation="email.send").inc()
            EMAIL_NOTIFICATIONS_TOTAL.labels(provider=provider_name, status="failed").inc()
            INTEGRATION_OPERATIONS_TOTAL.labels(provider=provider_name, operation="email.send", result="failed").inc()

            return {"status": "failed", "job_id": job_id, "error": str(exc)}


@celery_app.task(bind=True, max_retries=1)
def reconcile_calendar_appointments(self, limit: int = 50, auto_heal: bool = True) -> dict[str, Any]:
    """Run lightweight reconciliation across recent appointments to repair drift."""
    from fieldops.integrations.calendar.reconciliation import CalendarReconciliationService

    with SessionLocal() as session:
        service = CalendarReconciliationService(session)
        return service.reconcile_batch(limit=limit, auto_heal=auto_heal)

