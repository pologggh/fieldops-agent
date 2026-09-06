"""NotificationJob repository managing notification job records."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.db.models import NotificationJob


class NotificationJobRepository:
    """Repository managing lifecycle and idempotency of NotificationJob entities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, job_id: int) -> NotificationJob | None:
        """Get a notification job by ID."""
        stmt = select(NotificationJob).where(NotificationJob.id == job_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_appointment_job_schedule(
        self,
        appointment_id: int,
        job_type: str,
        scheduled_for: datetime,
    ) -> NotificationJob | None:
        """Find an existing notification job matching business uniqueness key."""
        stmt = (
            select(NotificationJob)
            .where(
                NotificationJob.appointment_id == appointment_id,
                NotificationJob.job_type == job_type,
                NotificationJob.scheduled_for == scheduled_for,
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_or_create(
        self,
        appointment_id: int,
        job_type: str,
        scheduled_for: datetime,
        status: str = "pending",
    ) -> tuple[NotificationJob, bool]:
        """Get an existing job or create a new one if it does not exist (created=True)."""
        existing = self.get_by_appointment_job_schedule(
            appointment_id=appointment_id,
            job_type=job_type,
            scheduled_for=scheduled_for,
        )
        if existing:
            return existing, False

        job = NotificationJob(
            appointment_id=appointment_id,
            job_type=job_type,
            scheduled_for=scheduled_for,
            status=status,
            attempt_count=0,
        )
        self.session.add(job)
        self.session.flush()
        return job, True

    create_or_get = get_or_create


    def get_by_appointment_id(self, appointment_id: int) -> list[NotificationJob]:
        """List all notification jobs associated with an appointment."""
        stmt = (
            select(NotificationJob)
            .where(NotificationJob.appointment_id == appointment_id)
            .order_by(NotificationJob.created_at.asc(), NotificationJob.id.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def mark_processing(self, job_id: int) -> NotificationJob | None:
        """Mark job as in processing and increment attempt count."""
        job = self.get(job_id)
        if job:
            job.status = "processing"
            job.attempt_count += 1
            self.session.flush()
        return job

    def mark_completed(
        self,
        job_id: int,
        provider: str | None = None,
        provider_message_id: str | None = None,
        sent_at: datetime | None = None,
    ) -> NotificationJob | None:
        """Mark job as completed successfully."""
        job = self.get(job_id)
        if job:
            job.status = "completed"
            if provider:
                job.provider = provider
            if provider_message_id:
                job.provider_message_id = provider_message_id
            if sent_at:
                job.sent_at = sent_at
            self.session.flush()
        return job

    def mark_skipped(self, job_id: int, reason: str | None = None) -> NotificationJob | None:
        """Mark job as skipped (e.g. appointment cancelled)."""
        job = self.get(job_id)
        if job:
            job.status = "skipped"
            if reason:
                job.last_error = reason
            self.session.flush()
        return job

    def mark_failed(self, job_id: int, error: str) -> NotificationJob | None:
        """Mark job as failed with error details."""
        job = self.get(job_id)
        if job:
            job.status = "failed"
            job.last_error = error
            self.session.flush()
        return job
