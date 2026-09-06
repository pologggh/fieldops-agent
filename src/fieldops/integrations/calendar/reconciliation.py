"""Lightweight Calendar Reconciliation Service to detect and remediate state drift."""

import logging
from typing import Any
from sqlalchemy.orm import Session

from fieldops.core.config import settings
from fieldops.db.models import Appointment, IntegrationRecord
from fieldops.integrations.calendar.base import CalendarClient
from fieldops.observability.metrics import CALENDAR_RECONCILIATION_DRIFT_TOTAL
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.integration_repository import IntegrationRepository

logger = logging.getLogger(__name__)


class CalendarReconciliationService:
    """Detects and repairs discrepancies between database appointments and external calendar events."""

    def __init__(
        self,
        session: Session,
        calendar_client: CalendarClient | None = None,
        provider_name: str | None = None,
    ) -> None:
        self.session = session
        if calendar_client is not None:
            self.client = calendar_client
        else:
            from fieldops.integrations import get_calendar_client
            self.client = get_calendar_client()
        self._provider_name = provider_name
        self.appt_repo = AppointmentRepository(session)
        self.integration_repo = IntegrationRepository(session)
        self.audit_repo = AuditLogRepository(session)

    @property
    def provider_name(self) -> str:
        if self._provider_name:
            return self._provider_name
        return f"{settings.CALENDAR_PROVIDER}_calendar"

    def reconcile_appointment(self, appointment_id: int, auto_heal: bool = True) -> dict[str, Any]:
        """Reconcile a single appointment with external calendar provider."""
        appointment = self.appt_repo.get_by_id(appointment_id)
        if not appointment:
            return {"status": "not_found", "appointment_id": appointment_id}

        record = self.integration_repo.get_by_provider_resource(
            self.provider_name, "appointment", appointment_id
        )

        drift_detected = None
        action_taken = None

        # Scenario A: Appointment is active (scheduled, in_progress, completed)
        if appointment.status in ("scheduled", "in_progress", "completed"):
            if not record or record.status != "synced" or not record.external_resource_id:
                drift_detected = "unsynced_local"
                logger.warning(
                    "Reconciliation: Appointment %s is %s but IntegrationRecord is %s",
                    appointment_id,
                    appointment.status,
                    record.status if record else "missing",
                )
                CALENDAR_RECONCILIATION_DRIFT_TOTAL.labels(
                    provider=self.provider_name, drift_type="unsynced_local"
                ).inc()

                if auto_heal:
                    from fieldops.tasks.integration_tasks import sync_appointment_calendar
                    sync_appointment_calendar.delay(appointment_id)
                    action_taken = "enqueued_sync"

            else:
                # Local record is synced; verify remote event existence
                remote_event = self.client.get_event(record.external_resource_id)
                if remote_event is None:
                    drift_detected = "missing_remote"
                    logger.warning(
                        "Reconciliation: Remote event %s for appointment %s not found on calendar provider",
                        record.external_resource_id,
                        appointment_id,
                    )
                    CALENDAR_RECONCILIATION_DRIFT_TOTAL.labels(
                        provider=self.provider_name, drift_type="missing_remote"
                    ).inc()

                    if auto_heal:
                        record.status = "failed"
                        record.last_error = "Remote event deleted or missing on provider"
                        self.session.commit()
                        from fieldops.tasks.integration_tasks import sync_appointment_calendar
                        sync_appointment_calendar.delay(appointment_id)
                        action_taken = "re_enqueued_sync"

                elif remote_event.status == "cancelled":
                    drift_detected = "remote_cancelled"
                    logger.warning(
                        "Reconciliation: Remote event %s for appointment %s is marked cancelled on provider",
                        record.external_resource_id,
                        appointment_id,
                    )
                    CALENDAR_RECONCILIATION_DRIFT_TOTAL.labels(
                        provider=self.provider_name, drift_type="remote_cancelled"
                    ).inc()

                    if auto_heal:
                        from fieldops.tasks.integration_tasks import sync_appointment_calendar
                        sync_appointment_calendar.delay(appointment_id)
                        action_taken = "re_enqueued_sync"

        # Scenario B: Appointment is cancelled
        elif appointment.status == "cancelled":
            if record and record.external_resource_id and record.status != "cancelled":
                remote_event = self.client.get_event(record.external_resource_id)
                if remote_event is not None:
                    drift_detected = "cancelled_appointment_active_remote"
                    logger.warning(
                        "Reconciliation: Appointment %s is cancelled but remote event %s is still active",
                        appointment_id,
                        record.external_resource_id,
                    )
                    CALENDAR_RECONCILIATION_DRIFT_TOTAL.labels(
                        provider=self.provider_name, drift_type="cancelled_appointment_active_remote"
                    ).inc()

                    if auto_heal:
                        self.client.cancel_event(record.external_resource_id)
                        self.integration_repo.mark_cancelled(record.id)
                        self.session.commit()
                        action_taken = "cancelled_remote_and_record"

        if drift_detected:
            self.audit_repo.create(
                entity_type="appointment",
                entity_id=str(appointment_id),
                action="calendar.reconciled",
                details={
                    "drift_type": drift_detected,
                    "action_taken": action_taken,
                    "provider": self.provider_name,
                },
            )
            self.session.commit()

        return {
            "status": "drift_repaired" if action_taken else ("drift_detected" if drift_detected else "in_sync"),
            "appointment_id": appointment_id,
            "drift": drift_detected,
            "action": action_taken,
            "provider": self.provider_name,
        }

    def reconcile_batch(self, limit: int = 50, auto_heal: bool = True) -> dict[str, Any]:
        """Scan recent appointments / integration records and repair inconsistencies."""
        # Query recent appointments
        recent_appointments = (
            self.session.query(Appointment)
            .order_by(Appointment.created_at.desc())
            .limit(limit)
            .all()
        )

        total_checked = len(recent_appointments)
        drifts_found = 0
        repaired = 0

        for appt in recent_appointments:
            res = self.reconcile_appointment(appt.id, auto_heal=auto_heal)
            if res.get("drift"):
                drifts_found += 1
                if res.get("action"):
                    repaired += 1

        return {
            "checked": total_checked,
            "drifts_detected": drifts_found,
            "repaired": repaired,
            "provider": self.provider_name,
        }
