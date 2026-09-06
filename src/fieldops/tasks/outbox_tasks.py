"""Transactional Outbox polling publisher."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from fieldops.db.session import SessionLocal
from fieldops.domain.services.scheduling import ensure_timezone
from fieldops.observability.metrics import (
    OUTBOX_PENDING,
    OUTBOX_PUBLISH_FAILURES_TOTAL,
)
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.outbox_repository import OutboxRepository
from fieldops.tasks.appointment_tasks import (
    send_appointment_reminder,
    send_followup_message,
)
from fieldops.tasks.celery_app import celery_app
from fieldops.tasks.integration_tasks import (
    cancel_appointment_calendar_event,
    send_appointment_confirmation,
    sync_appointment_calendar,
)

logger = logging.getLogger(__name__)


def calculate_reminder_time(start_time: datetime, now: datetime | None = None) -> datetime:
    """Determine the scheduled reminder time according to business rules.

    Rules:
    - Standard reminder: start_time - 24 hours.
    - If remaining time is < 24 hours but > 1 hour: start_time - 1 hour.
    - If remaining time is <= 1 hour or in the past: schedule immediately (now).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    norm_start = ensure_timezone(start_time)
    norm_now = ensure_timezone(now)

    t_minus_24h = norm_start - timedelta(hours=24)
    t_minus_1h = norm_start - timedelta(hours=1)

    if norm_now < t_minus_24h:
        return t_minus_24h
    elif norm_now < t_minus_1h:
        return t_minus_1h
    else:
        return norm_now


@celery_app.task
def publish_outbox_events(limit: int = 50) -> dict[str, Any]:
    """Poll pending outbox events from PostgreSQL and publish to Redis/Celery queue.

    If Redis is down or publish fails, the outbox event remains in status='pending',
    ensuring zero message loss and database consistency.
    """
    now = datetime.now(timezone.utc)
    processed_count = 0
    failed_count = 0

    with SessionLocal() as session:
        outbox_repo = OutboxRepository(session)
        appt_repo = AppointmentRepository(session)
        pending_events = outbox_repo.get_pending(limit=limit)

        OUTBOX_PENDING.set(len(pending_events))

        if not pending_events:
            return {"status": "ok", "processed": 0, "failed": 0}

        logger.info("Outbox publisher found %d pending events to process", len(pending_events))

        for event in pending_events:
            try:
                if event.event_type == "appointment.created":
                    appt_id = event.payload.get("appointment_id")
                    appt = appt_repo.get_by_id(appt_id)
                    if appt:
                        # 1. Dispatch calendar sync task
                        sync_appointment_calendar.apply_async(
                            kwargs={"appointment_id": appt.id}
                        )
                        logger.info("Dispatched sync_appointment_calendar for appt_id=%s", appt.id)

                        # 2. Dispatch email confirmation task
                        send_appointment_confirmation.apply_async(
                            kwargs={"appointment_id": appt.id}
                        )
                        logger.info("Dispatched send_appointment_confirmation for appt_id=%s", appt.id)

                        # 3. Dispatch scheduled reminder task
                        reminder_dt = calculate_reminder_time(appt.start_time, now=now)
                        delay_seconds = max(0, int((reminder_dt - now).total_seconds()))
                        send_appointment_reminder.apply_async(
                            kwargs={
                                "appointment_id": appt.id,
                                "scheduled_for_iso": reminder_dt.isoformat(),
                            },
                            countdown=delay_seconds,
                        )
                        logger.info(
                            "Dispatched send_appointment_reminder for appt_id=%s, countdown=%ds",
                            appt.id,
                            delay_seconds,
                        )
                    else:
                        logger.warning("Appointment id=%s not found for outbox event %s", appt_id, event.id)

                    outbox_repo.mark_processed(event.id)
                    session.commit()
                    processed_count += 1

                elif event.event_type == "appointment.completed":
                    appt_id = event.payload.get("appointment_id")
                    # Schedule follow-up task 1 hour later (3600 seconds)
                    send_followup_message.apply_async(
                        kwargs={"appointment_id": appt_id},
                        countdown=3600,
                    )
                    logger.info("Dispatched send_followup_message for appt_id=%s, countdown=3600s", appt_id)

                    outbox_repo.mark_processed(event.id)
                    session.commit()
                    processed_count += 1

                elif event.event_type == "appointment.cancelled":
                    appt_id = event.payload.get("appointment_id")
                    cancel_appointment_calendar_event.apply_async(
                        kwargs={"appointment_id": appt_id}
                    )
                    logger.info("Dispatched cancel_appointment_calendar_event for appt_id=%s", appt_id)

                    outbox_repo.mark_processed(event.id)
                    session.commit()
                    processed_count += 1

                else:
                    logger.warning("Unknown outbox event type: %s", event.event_type)
                    outbox_repo.mark_failed(event.id, f"unknown_event_type: {event.event_type}")
                    session.commit()
                    failed_count += 1

            except Exception as exc:
                # Critical: do NOT mark event as processed if publishing to message broker fails!
                # It remains pending in PostgreSQL so that once Redis recovers, it is retried.
                logger.error(
                    "Failed to publish outbox event id=%s (event_type=%s) to broker: %s. Event remains pending.",
                    event.id,
                    event.event_type,
                    exc,
                )
                OUTBOX_PUBLISH_FAILURES_TOTAL.inc()
                session.rollback()
                failed_count += 1

        OUTBOX_PENDING.set(max(0, len(pending_events) - processed_count))

    return {"status": "ok", "processed": processed_count, "failed": failed_count}
