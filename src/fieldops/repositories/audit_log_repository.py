from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.db.models import AuditLog


class AuditLogRepository:
    """Repository for AuditLog persistence and data access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        entity_type: str,
        entity_id: str | int,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Create and flush an audit log entry."""
        log = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            details=details,
        )
        self.session.add(log)
        self.session.flush()
        return log

    def list_by_entity(
        self, entity_type: str, entity_id: str | int
    ) -> list[AuditLog]:
        """List audit logs for a given entity ordered by creation time."""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == str(entity_id),
            )
            .order_by(AuditLog.created_at.asc())
        )
        return list(self.session.scalars(stmt).all())
