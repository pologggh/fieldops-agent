"""Repository for managing InboundEvent entities and channel-side idempotency."""

from datetime import datetime, timezone
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.db.models import InboundEvent

logger = logging.getLogger(__name__)


class InboundEventRepository:
    """Repository managing lifecycle and idempotency of InboundEvent entities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, event_id: int) -> InboundEvent | None:
        """Fetch an inbound event by its primary key."""
        return self.session.get(InboundEvent, event_id)

    def get_by_source_and_external_id(
        self, source: str, external_message_id: str
    ) -> InboundEvent | None:
        """Fetch an inbound event by channel source and external message/event ID."""
        stmt = (
            select(InboundEvent)
            .where(
                InboundEvent.source == source,
                InboundEvent.external_message_id == external_message_id,
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        source: str,
        request_hash: str,
        external_message_id: str | None = None,
        status: str = "received",
        request_id: str | None = None,
    ) -> InboundEvent:
        """Create a new InboundEvent record."""
        event = InboundEvent(
            source=source,
            external_message_id=external_message_id,
            request_hash=request_hash,
            status=status,
            request_id=request_id,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def mark_processing(
        self, event_id: int, request_id: str | None = None
    ) -> InboundEvent:
        """Transition inbound event to processing status."""
        event = self.get_by_id(event_id)
        if not event:
            raise ValueError(f"InboundEvent #{event_id} not found")
        event.status = "processing"
        if request_id:
            event.request_id = request_id
        self.session.flush()
        return event

    def mark_completed(
        self,
        event_id: int,
        request_id: str,
        service_request_id: int | None = None,
    ) -> InboundEvent:
        """Mark inbound event as completed with associated workflow request_id and service_request_id."""
        event = self.get_by_id(event_id)
        if not event:
            raise ValueError(f"InboundEvent #{event_id} not found")
        event.status = "completed"
        event.request_id = request_id
        if service_request_id is not None:
            event.service_request_id = service_request_id
        event.error_summary = None
        self.session.flush()
        return event

    def mark_failed(self, event_id: int, error_summary: str) -> InboundEvent:
        """Mark inbound event as failed with error summary."""
        event = self.get_by_id(event_id)
        if not event:
            raise ValueError(f"InboundEvent #{event_id} not found")
        event.status = "failed"
        event.error_summary = error_summary
        self.session.flush()
        return event
