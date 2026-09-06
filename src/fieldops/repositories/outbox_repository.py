"""Outbox repository managing transactional outbox events."""

from datetime import datetime
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fieldops.db.models import OutboxEvent


class OutboxRepository:
    """Repository managing lifecycle of OutboxEvent entities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        status: str = "pending",
    ) -> OutboxEvent:
        """Create a new outbox event within the current database transaction."""
        event = OutboxEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=payload,
            status=status,
            retry_count=0,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def get(self, event_id: int) -> OutboxEvent | None:
        """Get an outbox event by its ID."""
        stmt = select(OutboxEvent).where(OutboxEvent.id == event_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_pending(self, limit: int = 50) -> list[OutboxEvent]:
        """Fetch pending outbox events ordered by creation time."""
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending")
            .order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def mark_processed(self, event_id: int) -> OutboxEvent | None:
        """Mark an outbox event as successfully processed."""
        event = self.get(event_id)
        if event:
            event.status = "processed"
            event.processed_at = func.now()
            self.session.flush()
        return event

    def mark_failed(self, event_id: int, error: str) -> OutboxEvent | None:
        """Record a failure for an outbox event."""
        event = self.get(event_id)
        if event:
            event.retry_count += 1
            event.status = "failed"
            event.last_error = error
            self.session.flush()
        return event
