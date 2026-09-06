"""Idempotency repository managing idempotency records."""

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.db.models import IdempotencyRecord


class IdempotencyRepository:
    """Repository managing lifecycle of IdempotencyRecord entities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, operation: str) -> IdempotencyRecord | None:
        """Fetch an idempotency record by its key and operation type."""
        stmt = (
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.key == key,
                IdempotencyRecord.operation == operation,
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        key: str,
        operation: str,
        request_hash: str,
        status: str = "processing",
    ) -> IdempotencyRecord:
        """Insert a new idempotency record, defaulting to processing status."""
        record = IdempotencyRecord(
            key=key,
            operation=operation,
            request_hash=request_hash,
            status=status,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def mark_completed(
        self,
        key: str,
        operation: str,
        response_payload: dict[str, Any],
        resource_id: str | None = None,
    ) -> IdempotencyRecord | None:
        """Update an idempotency record to completed with its cached response payload."""
        record = self.get(key, operation)
        if record:
            record.status = "completed"
            record.response_payload = response_payload
            if resource_id is not None:
                record.resource_id = str(resource_id)
            self.session.flush()
        return record

    def mark_failed(self, key: str, operation: str) -> IdempotencyRecord | None:
        """Update an idempotency record to failed."""
        record = self.get(key, operation)
        if record:
            record.status = "failed"
            self.session.flush()
        return record
