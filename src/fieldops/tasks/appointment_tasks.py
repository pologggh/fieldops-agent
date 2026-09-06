"""Celery tasks for appointment reminders and follow-up notifications."""

from datetime import datetime, timezone
import logging
import random
from typing import Any
from celery.exceptions import MaxRetriesExceededError

from fieldops.core.logging import log_operation
from fieldops.db.session import SessionLocal
from fieldops.domain.services.scheduling import ensure_timezone
from fieldops.observability.metrics import (
    NOTIFICATION_FAILURES_TOTAL,
    NOTIFICATION_JOBS_TOTAL,
)
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.notification_job_repository import (
    NotificationJobRepository,
)
from fieldops.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_appointment_reminder(
    self,
    appointment_id: int,
    scheduled_for_iso: str | None = None,
) -> dict[str, Any]:
    """Execute simulated appointment reminder notification.

    Guarantees:
    1. Idempotency: Duplicate executions check notification_jobs table and avoid re-dispatch.
    2. Fresh DB Read: Checks PostgreSQL as Source of Truth.
    3. Status Guard: Skips sending if appointment was cancelled before execution.
    4. Safe Retry: Retries transient errors with exponential backoff up to max_retries.
    """
    task_id = self.request.id or "direct_exec"
    attempt = self.request.retries + 1

    # Parse scheduled_for timestamp
    if scheduled_for_iso:
        try:
            dt_sched = datetime.fromisoformat(scheduled_for_iso)
        except Exception:
            dt_sched = datetime.now(timezone.utc)
    else:
        dt_sched = datetime.now(timezone.utc)
    norm_scheduled_for = ensure_timezone(dt_sched)

    with SessionLocal() as session:
        notif_repo = NotificationJobRepository(session)
        appt_repo = AppointmentRepository(session)

        # 1. Idempotency Check
        existing_job = notif_repo.get_by_appointment_job_schedule(
            appointment_id=appointment_id,
            job_type="appointment_reminder",
            scheduled_for=norm_scheduled_for,
        )

        if existing_job:
            if existing_job.status == "completed":
                logger.info(
                    "Idempotency hit: Reminder already completed. job_id=%s, appointment_id=%s",
                    existing_job.id,
                    appointment_id,
                )
                return {
                    "status": "already_completed",
                    "job_id": existing_job.id,
                    "appointment_id": appointment_id,
                }
            if existing_job.status == "skipped":
                logger.info(
                    "Idempotency hit: Reminder already skipped. job_id=%s, appointment_id=%s",
                    existing_job.id,
                    appointment_id,
                )
                return {
                    "status": "already_skipped",
                    "job_id": existing_job.id,
                    "appointment_id": appointment_id,
                }

            # Update existing pending/processing job
            job = existing_job
            job.status = "processing"
            job.attempt_count = attempt
            session.flush()
            session.commit()
        else:
            job = notif_repo.create_or_get(
                appointment_id=appointment_id,
                job_type="appointment_reminder",
                scheduled_for=norm_scheduled_for,
                status="processing",
            )[0]
            job.attempt_count = attempt
            session.flush()
            session.commit()

        job_id = job.id

        # 2. Source of Truth & Status Guard
        appointment = appt_repo.get_by_id(appointment_id)
        if not appointment:
            logger.error(
                "Permanent error: Appointment id=%s not found in DB. Marking job failed.",
                appointment_id,
            )
            notif_repo.mark_failed(job_id, "appointment_not_found")
            session.commit()
            NOTIFICATION_JOBS_TOTAL.labels(job_type="appointment_reminder", status="failed").inc()
            NOTIFICATION_FAILURES_TOTAL.labels(job_type="appointment_reminder").inc()
            return {
                "status": "failed",
                "job_id": job_id,
                "error": "appointment_not_found",
            }

        if appointment.status == "cancelled":
            logger.info(
                "Status guard: Appointment id=%s is cancelled. Skipping reminder dispatch.",
                appointment_id,
            )
            notif_repo.mark_skipped(job_id, "appointment_cancelled")
            session.commit()
            NOTIFICATION_JOBS_TOTAL.labels(job_type="appointment_reminder", status="skipped").inc()
            return {
                "status": "skipped",
                "job_id": job_id,
                "reason": "appointment_cancelled",
            }

        # 3. Simulated Notification Execution
        try:
            logger.info(
                "Sending appointment reminder notification: task_id=%s, job_id=%s, appointment_id=%s, attempt=%s, scheduled_for=%s",
                task_id,
                job_id,
                appointment_id,
                attempt,
                norm_scheduled_for.isoformat(),
            )
            # Simulated notification message
            msg = (
                f"[SIMULATED REMINDER] Hello! Your appointment #{appointment.id} "
                f"starts at {appointment.start_time.isoformat()}."
            )
            logger.info("Notification payload delivered: %s", msg)

            # 4. Mark Completed in Database
            notif_repo.mark_completed(job_id)
            session.commit()
            NOTIFICATION_JOBS_TOTAL.labels(job_type="appointment_reminder", status="completed").inc()

            return {
                "status": "completed",
                "job_id": job_id,
                "appointment_id": appointment_id,
                "attempt_count": attempt,
            }

        except Exception as exc:
            logger.warning(
                "Transient error sending reminder for job_id=%s: %s",
                job_id,
                exc,
            )
            notif_repo.mark_failed(job_id, str(exc))
            session.commit()

            if self.request.retries >= self.max_retries:
                logger.error(
                    "Max retries exceeded for reminder job_id=%s, appointment_id=%s",
                    job_id,
                    appointment_id,
                )
                notif_repo.mark_failed(job_id, f"max_retries_exceeded: {exc}")
                session.commit()
                NOTIFICATION_JOBS_TOTAL.labels(job_type="appointment_reminder", status="failed").inc()
                NOTIFICATION_FAILURES_TOTAL.labels(job_type="appointment_reminder").inc()
                return {
                    "status": "failed",
                    "job_id": job_id,
                    "error": "max_retries_exceeded",
                }

            delay = 0 if getattr(self.request, "is_eager", False) else int(
                min(60 * (2 ** self.request.retries), 300) + random.uniform(1, 5)
            )
            raise self.retry(exc=exc, countdown=delay)



@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_followup_message(
    self,
    appointment_id: int,
    scheduled_for_iso: str | None = None,
) -> dict[str, Any]:
    """Execute simulated post-appointment follow-up notification."""
    task_id = self.request.id or "direct_exec"
    attempt = self.request.retries + 1

    if scheduled_for_iso:
        try:
            dt_sched = datetime.fromisoformat(scheduled_for_iso)
        except Exception:
            dt_sched = datetime.now(timezone.utc)
    else:
        dt_sched = datetime.now(timezone.utc)
    norm_scheduled_for = ensure_timezone(dt_sched)

    with SessionLocal() as session:
        notif_repo = NotificationJobRepository(session)
        appt_repo = AppointmentRepository(session)

        # 1. Idempotency Check
        existing_job = notif_repo.get_by_appointment_job_schedule(
            appointment_id=appointment_id,
            job_type="followup_message",
            scheduled_for=norm_scheduled_for,
        )

        if existing_job and existing_job.status == "completed":
            logger.info(
                "Idempotency hit: Followup already completed. job_id=%s, appointment_id=%s",
                existing_job.id,
                appointment_id,
            )
            return {
                "status": "already_completed",
                "job_id": existing_job.id,
                "appointment_id": appointment_id,
            }

        job, _ = notif_repo.get_or_create(
            appointment_id=appointment_id,
            job_type="followup_message",
            scheduled_for=norm_scheduled_for,
            status="processing",
        )
        job.attempt_count = attempt
        session.flush()
        session.commit()
        job_id = job.id

        # 2. Status Guard: Must be completed
        appointment = appt_repo.get_by_id(appointment_id)
        if not appointment:
            notif_repo.mark_failed(job_id, "appointment_not_found")
            session.commit()
            NOTIFICATION_JOBS_TOTAL.labels(job_type="followup_message", status="failed").inc()
            NOTIFICATION_FAILURES_TOTAL.labels(job_type="followup_message").inc()
            return {"status": "failed", "job_id": job_id, "error": "appointment_not_found"}

        if appointment.status != "completed":
            logger.info(
                "Status guard: Appointment id=%s is not completed (status=%s). Skipping followup.",
                appointment_id,
                appointment.status,
            )
            notif_repo.mark_skipped(job_id, f"appointment_status_{appointment.status}")
            session.commit()
            NOTIFICATION_JOBS_TOTAL.labels(job_type="followup_message", status="skipped").inc()
            return {
                "status": "skipped",
                "job_id": job_id,
                "reason": f"appointment_status_{appointment.status}",
            }

        # 3. Simulated Follow-up Execution
        try:
            logger.info(
                "Sending follow-up notification: task_id=%s, job_id=%s, appointment_id=%s",
                task_id,
                job_id,
                appointment_id,
            )
            msg = (
                f"[SIMULATED FOLLOW-UP] Thank you for choosing FieldOps! "
                f"How satisfied are you with service appointment #{appointment.id}?"
            )
            logger.info("Follow-up delivered: %s", msg)

            notif_repo.mark_completed(job_id)
            session.commit()
            NOTIFICATION_JOBS_TOTAL.labels(job_type="followup_message", status="completed").inc()

            return {
                "status": "completed",
                "job_id": job_id,
                "appointment_id": appointment_id,
                "attempt_count": attempt,
            }
        except Exception as exc:
            notif_repo.mark_failed(job_id, str(exc))
            session.commit()
            if self.request.retries >= self.max_retries:
                NOTIFICATION_JOBS_TOTAL.labels(job_type="followup_message", status="failed").inc()
                NOTIFICATION_FAILURES_TOTAL.labels(job_type="followup_message").inc()
                return {"status": "failed", "job_id": job_id, "error": "max_retries_exceeded"}
            delay = 0 if getattr(self.request, "is_eager", False) else 60
            raise self.retry(exc=exc, countdown=delay)

