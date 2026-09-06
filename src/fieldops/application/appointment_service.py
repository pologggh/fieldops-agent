from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fieldops.core.exceptions import ResourceNotFoundError
from fieldops.db.models import Appointment, Technician
from fieldops.domain.services.scheduling import ensure_timezone, has_time_conflict
from fieldops.observability.metrics import APPOINTMENT_CONFLICTS_TOTAL
from fieldops.repositories.appointment_repository import (
    BLOCKING_APPOINTMENT_STATUSES,
    AppointmentRepository,
)
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.outbox_repository import OutboxRepository
from fieldops.repositories.service_request_repository import (
    ServiceRequestRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinalizationResult:
    """Result of final appointment creation and conflict verification."""

    success: bool
    appointment_id: int | None
    appointment_status: str | None
    conflict_detected: bool
    finalization_status: str


@dataclass(frozen=True)
class RejectionResult:
    """Result of handling an operator rejection decision."""

    service_request_id: int
    finalization_status: str


class AppointmentService:
    """Application domain service managing atomic appointment creation, conflict re-checking, and audit logging."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.appointment_repo = AppointmentRepository(session)
        self.service_request_repo = ServiceRequestRepository(session)
        self.audit_log_repo = AuditLogRepository(session)
        self.outbox_repo = OutboxRepository(session)


    def finalize_appointment(
        self,
        service_request_id: int,
        technician_id: int,
        start_time: datetime | str,
        end_time: datetime | str,
    ) -> FinalizationResult:
        """Atomically re-verify conflicts and create an appointment record.

        Transaction boundary:
        BEGIN
            1. Idempotency check: if appointment already exists for this service_request_id, return it.
            2. Lock target technician row (SELECT ... FOR UPDATE) to serialize concurrent bookings.
            3. Final conflict re-check against overlapping active appointments.
            4. If conflict detected:
               - Update ServiceRequest.status = 'needs_rescheduling'
               - Write AuditLog action = 'appointment.conflict'
               COMMIT
               Return conflict result.
            5. If no conflict:
               - Create Appointment (status = 'scheduled')
               - Update ServiceRequest.status = 'scheduled'
               - Write AuditLog action = 'appointment.created'
               COMMIT
               Return success result.
        ROLLBACK on unexpected failure or database constraint violation.
        """
        # Parse datetime inputs if strings
        dt_start = (
            datetime.fromisoformat(start_time)
            if isinstance(start_time, str)
            else start_time
        )
        dt_end = (
            datetime.fromisoformat(end_time)
            if isinstance(end_time, str)
            else end_time
        )
        norm_start = ensure_timezone(dt_start)
        norm_end = ensure_timezone(dt_end)

        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )

        try:
            with tx_context:
                # 1. Idempotency check: prevent duplicate appointments for the same service request
                existing_appt = self.appointment_repo.get_by_service_request_id(
                    service_request_id
                )
                if (
                    existing_appt is not None
                    and existing_appt.status in BLOCKING_APPOINTMENT_STATUSES
                ):
                    logger.info(
                        "Idempotent finalize: Appointment id=%s already exists for service_request_id=%s",
                        existing_appt.id,
                        service_request_id,
                    )
                    return FinalizationResult(
                        success=True,
                        appointment_id=existing_appt.id,
                        appointment_status=existing_appt.status,
                        conflict_detected=False,
                        finalization_status="completed",
                    )

                # 2. Acquire row-level exclusive lock on the Technician resource
                lock_stmt = (
                    select(Technician)
                    .where(Technician.id == technician_id)
                    .with_for_update()
                )
                self.session.execute(lock_stmt).scalar_one_or_none()

                # 3. Final conflict re-check using deterministic overlap formula
                blocking_appts = (
                    self.appointment_repo.get_blocking_by_technician_and_window(
                        technician_id=technician_id,
                        window_start=norm_start,
                        window_end=norm_end,
                    )
                )

                conflict_found = any(
                    has_time_conflict(
                        norm_start, norm_end, appt.start_time, appt.end_time
                    )
                    for appt in blocking_appts
                )

                if conflict_found:
                    logger.warning(
                        "Final conflict detected for technician_id=%s during window %s - %s",
                        technician_id,
                        norm_start.isoformat(),
                        norm_end.isoformat(),
                    )
                    APPOINTMENT_CONFLICTS_TOTAL.inc()
                    self.service_request_repo.update_status(
                        service_request_id, "needs_rescheduling"
                    )
                    self.audit_log_repo.create(
                        entity_type="service_request",
                        entity_id=service_request_id,
                        action="appointment.conflict",
                        details={
                            "technician_id": technician_id,
                            "start_time": norm_start.isoformat(),
                            "end_time": norm_end.isoformat(),
                            "conflicting_appointment_ids": [
                                a.id for a in blocking_appts
                            ],
                        },
                    )
                    # Exits transaction block successfully committing status update and audit log
                    return FinalizationResult(
                        success=False,
                        appointment_id=None,
                        appointment_status=None,
                        conflict_detected=True,
                        finalization_status="conflict",
                    )

                # 4. No conflict: create Appointment and update ServiceRequest
                appointment = self.appointment_repo.create(
                    service_request_id=service_request_id,
                    technician_id=technician_id,
                    start_time=norm_start,
                    end_time=norm_end,
                    status="scheduled",
                )

                self.service_request_repo.update_status(
                    service_request_id, "scheduled"
                )

                self.audit_log_repo.create(
                    entity_type="appointment",
                    entity_id=appointment.id,
                    action="appointment.created",
                    details={
                        "service_request_id": service_request_id,
                        "technician_id": technician_id,
                        "start_time": norm_start.isoformat(),
                        "end_time": norm_end.isoformat(),
                        "status": "scheduled",
                    },
                )

                self.outbox_repo.create(
                    event_type="appointment.created",
                    aggregate_type="appointment",
                    aggregate_id=str(appointment.id),
                    payload={"appointment_id": appointment.id},
                )

                logger.info(
                    "Appointment successfully created: appointment_id=%s, service_request_id=%s, tech_id=%s",
                    appointment.id,
                    service_request_id,
                    technician_id,
                )

                return FinalizationResult(
                    success=True,
                    appointment_id=appointment.id,
                    appointment_status="scheduled",
                    conflict_detected=False,
                    finalization_status="completed",
                )

        except IntegrityError as e:
            # Caught if PostgreSQL Exclusion Constraint (or unique constraint) triggers under concurrency
            logger.warning(
                "Database integrity / exclusion violation during appointment finalization: %s",
                e,
            )
            APPOINTMENT_CONFLICTS_TOTAL.inc()
            # Record conflict in a separate transaction
            try:
                tx_rec = (
                    self.session.begin_nested()
                    if self.session.in_transaction()
                    else self.session.begin()
                )
                with tx_rec:
                    self.service_request_repo.update_status(
                        service_request_id, "needs_rescheduling"
                    )
                    self.audit_log_repo.create(
                        entity_type="service_request",
                        entity_id=service_request_id,
                        action="appointment.conflict",
                        details={
                            "error": "database_exclusion_violation",
                            "message": str(e.orig) if hasattr(e, "orig") else str(e),
                        },
                    )
            except Exception as inner_e:
                logger.error("Failed to record conflict audit log: %s", inner_e)

            return FinalizationResult(
                success=False,
                appointment_id=None,
                appointment_status=None,
                conflict_detected=True,
                finalization_status="conflict",
            )
        except Exception as e:
            logger.error("Unexpected failure during appointment finalization: %s", e)
            raise

    def handle_rejection(
        self,
        service_request_id: int,
        reason: str | None = None,
    ) -> RejectionResult:
        """Atomically update service request to rejected and record audit log."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            self.service_request_repo.update_status(
                service_request_id, "rejected"
            )
            self.audit_log_repo.create(
                entity_type="service_request",

                entity_id=service_request_id,
                action="appointment.rejected",
                details={"reason": reason},
            )
            logger.info(
                "ServiceRequest id=%s marked as rejected, reason=%s",
                service_request_id,
                reason,
            )

        return RejectionResult(
            service_request_id=service_request_id,
            finalization_status="rejected",
        )

    def complete_appointment(
        self,
        appointment_id: int,
        completion_notes: str | None = None,
        resolution_summary: str | None = None,
    ) -> Appointment:
        """Mark an appointment as completed via ServiceLifecycleService."""
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        lifecycle = ServiceLifecycleService(self.session)
        return lifecycle.complete_service(
            appointment_id=appointment_id,
            completion_notes=completion_notes,
            resolution_summary=resolution_summary,
            actor_type="operator",
        )

    def cancel_appointment(
        self, appointment_id: int, reason: str | None = None
    ) -> Appointment:
        """Cancel an appointment via ServiceLifecycleService."""
        from fieldops.application.service_lifecycle_service import ServiceLifecycleService
        lifecycle = ServiceLifecycleService(self.session)
        _, appt = lifecycle.cancel_request(
            appointment_id=appointment_id,
            reason=reason,
            actor_type="operator",
        )
        if not appt:
            raise ResourceNotFoundError(f"Appointment {appointment_id} not found")
        return appt


