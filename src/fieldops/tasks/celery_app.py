"""Celery application configuration for FieldOps Agent."""

import logging
from celery import Celery

from fieldops.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery application
celery_app = Celery(
    "fieldops",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "fieldops.tasks.appointment_tasks",
        "fieldops.tasks.outbox_tasks",
    ],
)

# Celery Configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.BUSINESS_TIMEZONE,
    enable_utc=True,
    # Late ACK: send acknowledgement only after task succeeds or fails permanently.
    # Prevents message loss if worker is killed during task execution (At-least-once delivery).
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Prefetch limits: 1 task per worker concurrency slot for fair scheduling
    worker_prefetch_multiplier=1,
    # Periodic tasks (Celery Beat)
    beat_schedule={
        "publish-outbox-events-every-minute": {
            "task": "fieldops.tasks.outbox_tasks.publish_outbox_events",
            "schedule": 60.0,
        },
    },
)
