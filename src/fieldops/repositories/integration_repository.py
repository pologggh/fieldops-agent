"""Repository for managing third-party IntegrationRecord lifecycle."""

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.db.models import IntegrationRecord

logger = logging.getLogger(__name__)


class IntegrationRepository:
    """Encapsulates database access and concurrency control for IntegrationRecord."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_provider_resource(
        self, provider: str, resource_type: str, local_resource_id: int
    ) -> IntegrationRecord | None:
        """Retrieve integration record by composite unique key."""
        stmt = (
            select(IntegrationRecord)
            .where(
                IntegrationRecord.provider == provider,
                IntegrationRecord.resource_type == resource_type,
                IntegrationRecord.local_resource_id == local_resource_id,
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_or_create_for_update(
        self,
        provider: str,
        resource_type: str,
        local_resource_id: int,
        default_status: str = "pending",
    ) -> tuple[IntegrationRecord, bool]:
        """Fetch existing record with row-level lock, or insert a new one if not present."""
        stmt = (
            select(IntegrationRecord)
            .where(
                IntegrationRecord.provider == provider,
                IntegrationRecord.resource_type == resource_type,
                IntegrationRecord.local_resource_id == local_resource_id,
            )
            .with_for_update()
        )
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing:
            return existing, False

        record = IntegrationRecord(
            provider=provider,
            resource_type=resource_type,
            local_resource_id=local_resource_id,
            status=default_status,
            attempt_count=0,
        )
        self.session.add(record)
        self.session.flush()
        return record, True

    def mark_synced(
        self, record_id: int, external_resource_id: str
    ) -> IntegrationRecord | None:
        """Mark record as successfully synchronized."""
        record = self.session.get(IntegrationRecord, record_id)
        if record:
            record.external_resource_id = external_resource_id
            record.status = "synced"
            record.last_error = None
            self.session.flush()
        return record

    def mark_failed(
        self, record_id: int, error_message: str
    ) -> IntegrationRecord | None:
        """Mark record as failed with error details."""
        record = self.session.get(IntegrationRecord, record_id)
        if record:
            record.status = "failed"
            record.last_error = error_message
            self.session.flush()
        return record

    def mark_cancelled(self, record_id: int) -> IntegrationRecord | None:
        """Mark record as cancelled."""
        record = self.session.get(IntegrationRecord, record_id)
        if record:
            record.status = "cancelled"
            self.session.flush()
        return record

    def get_by_appointment_id(self, appointment_id: int) -> list[IntegrationRecord]:
        """Fetch all integration records related to an appointment."""
        stmt = (
            select(IntegrationRecord)
            .where(
                IntegrationRecord.resource_type == "appointment",
                IntegrationRecord.local_resource_id == appointment_id,
            )
        )
        return list(self.session.execute(stmt).scalars().all())
