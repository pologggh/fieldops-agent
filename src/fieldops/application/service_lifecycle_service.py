"""Service Lifecycle Service (Phase 24).

Centralized state transition engine for ServiceRequest and Appointment lifecycles:
- Created -> Scheduled -> In Progress -> Completed
- Cancelled (with race-handling against Completed)
- Reschedule Requested -> Rescheduled / Rejected
- Technician Reassignment
- Dynamic capability computation
- Transactional Outbox and Audit Log integration
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.core.exceptions import (
    AppointmentAlreadyCancelledError,
    AppointmentAlreadyCompletedError,
    AppointmentNotReschedulableError,
    InvalidStateTransitionError,
    ReassignmentNoCandidateError,
    RequestNotCancellableError,
    ResourceNotFoundError,
)
from fieldops.db.models import (
    Appointment,
    AuditLog,
    OutboxEvent,
    RescheduleRequest,
    ServiceRequest,
    Technician,
)
from fieldops.observability.metrics import (
    APPOINTMENTS_IN_PROGRESS_GAUGE,
    REASSIGNMENTS_TOTAL,
    REQUESTS_CANCELLED_TOTAL,
    REQUESTS_COMPLETED_TOTAL,
    RESCHEDULE_REQUESTS_TOTAL,
    RESCHEDULE_SUCCESS_TOTAL,
)
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.audit_log_repository import AuditLogRepository
from fieldops.repositories.outbox_repository import OutboxRepository
from fieldops.repositories.service_request_repository import ServiceRequestRepository
from fieldops.schemas.lifecycle_schemas import LifecycleCapabilitiesView

logger = logging.getLogger(__name__)


class ServiceLifecycleService:
    """Orchestrates all state transitions for ServiceRequests and Appointments."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.appointment_repo = AppointmentRepository(session)
        self.service_request_repo = ServiceRequestRepository(session)
        self.audit_log_repo = AuditLogRepository(session)
        self.outbox_repo = OutboxRepository(session)

    # --------------------------------------------------------------------------
    # 1. Capabilities Computation
    # --------------------------------------------------------------------------

    def compute_capabilities(
        self,
        appointment: Optional[Appointment] = None,
        service_request: Optional[ServiceRequest] = None,
        role: str = "operator",
    ) -> LifecycleCapabilitiesView:
        """Compute permissible state actions for an appointment/request based on caller role and current state."""
        appt_status = appointment.status if appointment else None
        sr_status = service_request.status if service_request else (
            appointment.service_request.status if (appointment and appointment.service_request) else None
        )

        # Base flags
        can_start = False
        can_complete = False
        can_cancel = False
        can_reschedule = False
        can_reassign = False

        if appointment:
            # 1. Start: only from scheduled/confirmed
            if appt_status in ["scheduled", "confirmed"]:
                can_start = (role in ["operator", "admin", "technician"])

            # 2. Complete: from in_progress or scheduled/confirmed
            if appt_status in ["in_progress", "scheduled", "confirmed"]:
                can_complete = (role in ["operator", "admin", "technician"])

            # 3. Cancel:
            if appt_status not in ["completed", "cancelled"]:
                if role == "customer":
                    # Customer cannot cancel in-progress service
                    can_cancel = (appt_status != "in_progress" and sr_status not in ["in_progress", "completed", "cancelled"])
                else:
                    can_cancel = True

            # 4. Reschedule:
            if appt_status not in ["completed", "cancelled"]:
                if role == "customer":
                    # Customer cannot reschedule in-progress service
                    can_reschedule = (appt_status != "in_progress" and sr_status not in ["in_progress", "completed", "cancelled"])
                else:
                    can_reschedule = (appt_status != "in_progress")

            # 5. Reassign:
            if appt_status not in ["completed", "cancelled", "in_progress"]:
                can_reassign = (role in ["operator", "admin"])

        elif service_request:
            # Request without active appointment
            if sr_status not in ["completed", "cancelled", "in_progress"]:
                can_cancel = True
                can_reschedule = sr_status in ["waiting_for_approval", "needs_rescheduling", "conflict"]

        return LifecycleCapabilitiesView(
            can_start=can_start,
            can_complete=can_complete,
            can_cancel=can_cancel,
            can_reschedule=can_reschedule,
            can_reassign=can_reassign,
        )

    # --------------------------------------------------------------------------
    # 2. Start Service
    # --------------------------------------------------------------------------

    def start_service(
        self,
        appointment_id: int,
        started_at: Optional[datetime] = None,
        actor_type: str = "operator",
        actor_id: Optional[str] = None,
    ) -> Appointment:
        """Advance appointment and service request from scheduled -> in_progress."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            appointment = self.appointment_repo.get_by_id(appointment_id)
            if not appointment:
                raise ResourceNotFoundError(f"Appointment {appointment_id} not found")

            # Concurrency & state validation
            if appointment.status == "in_progress":
                logger.info("Appointment %s is already in_progress (idempotent).", appointment_id)
                return appointment

            if appointment.status == "completed":
                raise AppointmentAlreadyCompletedError(
                    f"Cannot start appointment {appointment_id} because it is already completed."
                )

            if appointment.status == "cancelled":
                raise AppointmentAlreadyCancelledError(
                    f"Cannot start appointment {appointment_id} because it has been cancelled."
                )

            if appointment.status not in ["scheduled", "confirmed"]:
                raise InvalidStateTransitionError(
                    f"Cannot start appointment in status '{appointment.status}'. Must be scheduled or confirmed."
                )

            now_utc = started_at or datetime.now(timezone.utc)
            appointment.status = "in_progress"
            appointment.started_at = now_utc

            # Synchronize ServiceRequest
            sr = None
            if appointment.service_request_id:
                sr = self.service_request_repo.get_by_id(appointment.service_request_id)
                if sr and sr.status != "in_progress":
                    self.service_request_repo.update_status(sr.id, "in_progress")
                    self.audit_log_repo.create(
                        entity_type="service_request",
                        entity_id=str(sr.id),
                        action="service_request.in_progress",
                        details={
                            "appointment_id": appointment.id,
                            "actor_type": actor_type,
                            "actor_id": actor_id,
                            "started_at": now_utc.isoformat(),
                        },
                    )

            # Audit Log
            self.audit_log_repo.create(
                entity_type="appointment",
                entity_id=str(appointment.id),
                action="appointment.started",
                details={
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                    "started_at": now_utc.isoformat(),
                },
            )

            # Outbox Event
            self.outbox_repo.create(
                event_type="appointment.started",
                aggregate_type="appointment",
                aggregate_id=str(appointment.id),
                payload={
                    "appointment_id": appointment.id,
                    "service_request_id": sr.id if sr else None,
                    "started_at": now_utc.isoformat(),
                },
            )

            try:
                APPOINTMENTS_IN_PROGRESS_GAUGE.inc()
            except Exception:
                pass

            logger.info("Appointment %s moved to in_progress by %s", appointment_id, actor_type)
            return appointment

    # --------------------------------------------------------------------------
    # 3. Complete Service
    # --------------------------------------------------------------------------

    def complete_service(
        self,
        appointment_id: int,
        completion_notes: Optional[str] = None,
        resolution_summary: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        actor_type: str = "operator",
        actor_id: Optional[str] = None,
    ) -> Appointment:
        """Mark appointment and service request completed (with double-complete idempotency and cancel-race detection)."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            appointment = self.appointment_repo.get_by_id(appointment_id)
            if not appointment:
                raise ResourceNotFoundError(f"Appointment {appointment_id} not found")

            # 1. Double-Complete Idempotency
            if appointment.status == "completed":
                logger.info("Appointment %s already completed. Returning idempotently (no duplicate side effects).", appointment_id)
                return appointment

            # 2. Complete vs Cancel Race
            if appointment.status == "cancelled":
                raise AppointmentAlreadyCancelledError(
                    f"Cannot complete appointment {appointment_id} because it has already been cancelled."
                )

            if appointment.status not in ["in_progress", "scheduled", "confirmed"]:
                raise InvalidStateTransitionError(
                    f"Cannot complete appointment in status '{appointment.status}'."
                )

            now_utc = completed_at or datetime.now(timezone.utc)
            prev_status = appointment.status
            appointment.status = "completed"
            appointment.completed_at = now_utc
            if not appointment.started_at:
                appointment.started_at = appointment.start_time
            if completion_notes:
                appointment.completion_notes = completion_notes
            if resolution_summary:
                appointment.resolution_summary = resolution_summary

            # Synchronize ServiceRequest
            sr = None
            if appointment.service_request_id:
                sr = self.service_request_repo.get_by_id(appointment.service_request_id)
                if sr and sr.status != "completed":
                    self.service_request_repo.update_status(sr.id, "completed")
                    self.audit_log_repo.create(
                        entity_type="service_request",
                        entity_id=str(sr.id),
                        action="service_request.completed",
                        details={
                            "appointment_id": appointment.id,
                            "actor_type": actor_type,
                            "actor_id": actor_id,
                            "completion_notes": completion_notes,
                            "resolution_summary": resolution_summary,
                        },
                    )

            # Audit Log
            self.audit_log_repo.create(
                entity_type="appointment",
                entity_id=str(appointment.id),
                action="appointment.completed",
                details={
                    "appointment_id": appointment.id,
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                    "completed_at": now_utc.isoformat(),
                    "completion_notes": completion_notes,
                    "resolution_summary": resolution_summary,
                },
            )

            # Transactional Outbox Event (triggers 1hr follow-up asynchronously)
            self.outbox_repo.create(
                event_type="appointment.completed",
                aggregate_type="appointment",
                aggregate_id=str(appointment.id),
                payload={
                    "appointment_id": appointment.id,
                    "service_request_id": sr.id if sr else None,
                    "completed_at": now_utc.isoformat(),
                },
            )

            if prev_status == "in_progress":
                try:
                    APPOINTMENTS_IN_PROGRESS_GAUGE.dec()
                except Exception:
                    pass

            try:
                REQUESTS_COMPLETED_TOTAL.inc()
            except Exception:
                pass

            logger.info("Appointment %s and ServiceRequest completed successfully.", appointment_id)
            return appointment

    # --------------------------------------------------------------------------
    # 4. Cancel Request / Appointment
    # --------------------------------------------------------------------------

    def cancel_request(
        self,
        service_request_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        reason: Optional[str] = None,
        actor_type: str = "operator",
        actor_id: Optional[str] = None,
    ) -> Tuple[Optional[ServiceRequest], Optional[Appointment]]:
        """Atomically cancel a service request and/or its active appointment."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            appointment: Optional[Appointment] = None
            sr: Optional[ServiceRequest] = None

            if appointment_id:
                appointment = self.appointment_repo.get_by_id(appointment_id)
                if not appointment:
                    raise ResourceNotFoundError(f"Appointment {appointment_id} not found")
                if appointment.service_request_id:
                    sr = self.service_request_repo.get_by_id(appointment.service_request_id)

            if service_request_id:
                sr = self.service_request_repo.get_by_id(service_request_id)
                if not sr:
                    raise ResourceNotFoundError(f"ServiceRequest {service_request_id} not found")
                if not appointment:
                    appointment = (
                        self.session.query(Appointment)
                        .filter(Appointment.service_request_id == sr.id, Appointment.status != "cancelled")
                        .order_by(Appointment.id.desc())
                        .first()
                    )

            # Concurrency & validation against Completed state
            if (appointment and appointment.status == "completed") or (sr and sr.status == "completed"):
                raise AppointmentAlreadyCompletedError(
                    "Cannot cancel a service that is already completed."
                )

            # Check if customer is attempting to cancel an in-progress service
            if actor_type == "customer":
                if (appointment and appointment.status == "in_progress") or (sr and sr.status == "in_progress"):
                    raise RequestNotCancellableError(
                        "Customer cannot cancel a service order that is currently in progress."
                    )

            # If both are already cancelled, return idempotently
            is_already_cancelled = (
                (appointment is None or appointment.status == "cancelled")
                and (sr is None or sr.status == "cancelled")
            )
            if is_already_cancelled:
                logger.info("ServiceRequest / Appointment already cancelled. Returning idempotently.")
                return sr, appointment

            # Perform cancellation
            if appointment and appointment.status != "cancelled":
                prev_status = appointment.status
                appointment.status = "cancelled"
                if prev_status == "in_progress":
                    try:
                        APPOINTMENTS_IN_PROGRESS_GAUGE.dec()
                    except Exception:
                        pass

                self.audit_log_repo.create(
                    entity_type="appointment",
                    entity_id=str(appointment.id),
                    action="appointment.cancelled",
                    details={
                        "actor_type": actor_type,
                        "actor_id": actor_id,
                        "reason": reason,
                    },
                )
                self.outbox_repo.create(
                    event_type="appointment.cancelled",
                    aggregate_type="appointment",
                    aggregate_id=str(appointment.id),
                    payload={
                        "appointment_id": appointment.id,
                        "reason": reason,
                    },
                )

            if sr and sr.status != "cancelled":
                sr.status = "cancelled"
                self.audit_log_repo.create(
                    entity_type="service_request",
                    entity_id=str(sr.id),
                    action="service_request.cancelled",
                    details={
                        "actor_type": actor_type,
                        "actor_id": actor_id,
                        "reason": reason,
                    },
                )

            # Cancel any pending reschedule requests associated with this SR or appointment
            if sr:
                pending_reschedules = (
                    self.session.query(RescheduleRequest)
                    .filter(RescheduleRequest.service_request_id == sr.id, RescheduleRequest.status == "pending")
                    .all()
                )
                for pr in pending_reschedules:
                    pr.status = "cancelled"

            try:
                REQUESTS_CANCELLED_TOTAL.inc()
            except Exception:
                pass

            logger.info("ServiceRequest %s and Appointment %s cancelled by %s",
                        sr.id if sr else None, appointment.id if appointment else None, actor_type)
            return sr, appointment

    # --------------------------------------------------------------------------
    # 5. Reschedule Request
    # --------------------------------------------------------------------------

    def request_reschedule(
        self,
        service_request_id: int,
        preferred_time: str,
        reason: Optional[str] = None,
        requested_by_type: str = "customer",
        requested_by_id: Optional[str] = None,
    ) -> RescheduleRequest:
        """Create a formal RescheduleRequest and update ServiceRequest status."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            sr = self.service_request_repo.get_by_id(service_request_id)
            if not sr:
                raise ResourceNotFoundError(f"ServiceRequest {service_request_id} not found")

            if sr.status in ["completed", "cancelled"]:
                raise AppointmentNotReschedulableError(
                    f"Cannot reschedule a service request that is {sr.status}."
                )

            if requested_by_type == "customer" and sr.status == "in_progress":
                raise AppointmentNotReschedulableError(
                    "Customer cannot request rescheduling for an in-progress service."
                )

            appt = (
                self.session.query(Appointment)
                .filter(Appointment.service_request_id == sr.id, Appointment.status != "cancelled")
                .order_by(Appointment.id.desc())
                .first()
            )
            if not appt:
                raise ResourceNotFoundError(f"No active appointment found for ServiceRequest {service_request_id}")

            if appt.status in ["completed", "cancelled"]:
                raise AppointmentNotReschedulableError(
                    f"Cannot reschedule an appointment in status '{appt.status}'."
                )

            if requested_by_type == "customer" and appt.status == "in_progress":
                raise AppointmentNotReschedulableError(
                    "Customer cannot request rescheduling for an in-progress appointment."
                )

            # Check if there is already a pending reschedule request
            existing_pending = (
                self.session.query(RescheduleRequest)
                .filter(
                    RescheduleRequest.service_request_id == sr.id,
                    RescheduleRequest.status == "pending",
                )
                .first()
            )
            if existing_pending:
                # Update existing pending request
                existing_pending.preferred_time = preferred_time
                existing_pending.reason = reason
                existing_pending.requested_by_type = requested_by_type
                existing_pending.requested_by_id = requested_by_id
                resched_req = existing_pending
            else:
                resched_req = RescheduleRequest(
                    service_request_id=sr.id,
                    appointment_id=appt.id,
                    requested_by_type=requested_by_type,
                    requested_by_id=requested_by_id,
                    preferred_time=preferred_time,
                    reason=reason,
                    status="pending",
                )
                self.session.add(resched_req)
                self.session.flush()

            # Mark SR as needs_rescheduling
            sr.status = "needs_rescheduling"

            self.audit_log_repo.create(
                entity_type="service_request",
                entity_id=str(sr.id),
                action="service_request.reschedule_requested",
                details={
                    "reschedule_request_id": resched_req.id,
                    "requested_by_type": requested_by_type,
                    "requested_by_id": requested_by_id,
                    "preferred_time": (
                        preferred_time.isoformat()
                        if hasattr(preferred_time, "isoformat")
                        else str(preferred_time)
                        if preferred_time
                        else None
                    ),
                    "reason": reason,
                },
            )

            try:
                RESCHEDULE_REQUESTS_TOTAL.inc()
            except Exception:
                pass

            logger.info("RescheduleRequest %s created for SR %s", resched_req.id, sr.id)
            return resched_req

    # --------------------------------------------------------------------------
    # 6. Approve Reschedule
    # --------------------------------------------------------------------------

    def approve_reschedule(
        self,
        reschedule_request_id: int,
        start_time: datetime,
        end_time: datetime,
        technician_id: Optional[int] = None,
        operator_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Tuple[RescheduleRequest, Appointment]:
        """Approve reschedule: cancel old appointment and create replacement appointment preserving history."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            resched_req = self.session.get(RescheduleRequest, reschedule_request_id)
            if not resched_req:
                raise ResourceNotFoundError(f"RescheduleRequest {reschedule_request_id} not found")

            if resched_req.status != "pending":
                raise InvalidStateTransitionError(
                    f"RescheduleRequest {reschedule_request_id} is in status '{resched_req.status}', cannot approve."
                )

            old_appt = self.appointment_repo.get_by_id(resched_req.appointment_id)
            if not old_appt:
                raise ResourceNotFoundError(f"Prior appointment {resched_req.appointment_id} not found")

            target_tech_id = technician_id or old_appt.technician_id

            # Create replacement appointment
            new_appt = Appointment(
                service_request_id=resched_req.service_request_id,
                technician_id=target_tech_id,
                start_time=start_time,
                end_time=end_time,
                status="scheduled",
                rescheduled_from_appointment_id=old_appt.id,
            )
            self.session.add(new_appt)
            self.session.flush()

            # Mark old appointment as cancelled with pointer to replacement
            old_appt.status = "cancelled"
            old_appt.replaced_by_appointment_id = new_appt.id

            # Update RescheduleRequest
            resched_req.status = "approved"
            resched_req.reviewed_by = operator_id
            resched_req.replacement_appointment_id = new_appt.id

            # Update ServiceRequest status to scheduled
            sr = self.service_request_repo.get_by_id(resched_req.service_request_id)
            if sr:
                sr.status = "scheduled"

            # Audit logs
            self.audit_log_repo.create(
                entity_type="reschedule_request",
                entity_id=str(resched_req.id),
                action="reschedule_request.approved",
                details={
                    "operator_id": operator_id,
                    "old_appointment_id": old_appt.id,
                    "new_appointment_id": new_appt.id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "notes": notes,
                },
            )
            self.audit_log_repo.create(
                entity_type="appointment",
                entity_id=str(new_appt.id),
                action="appointment.rescheduled_created",
                details={
                    "rescheduled_from_appointment_id": old_appt.id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                },
            )

            # Outbox events: Cancel old calendar event + create new calendar event
            self.outbox_repo.create(
                event_type="appointment.cancelled",
                aggregate_type="appointment",
                aggregate_id=str(old_appt.id),
                payload={"appointment_id": old_appt.id, "reason": "Rescheduled"},
            )
            self.outbox_repo.create(
                event_type="appointment.created",
                aggregate_type="appointment",
                aggregate_id=str(new_appt.id),
                payload={"appointment_id": new_appt.id},
            )

            try:
                RESCHEDULE_SUCCESS_TOTAL.inc()
            except Exception:
                pass

            logger.info("RescheduleRequest %s approved: old appt %s -> new appt %s",
                        resched_req.id, old_appt.id, new_appt.id)
            return resched_req, new_appt

    # --------------------------------------------------------------------------
    # 7. Reject Reschedule
    # --------------------------------------------------------------------------

    def reject_reschedule(
        self,
        reschedule_request_id: int,
        rejection_reason: str,
        operator_id: Optional[str] = None,
    ) -> RescheduleRequest:
        """Reject reschedule request and return ServiceRequest to scheduled state."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            resched_req = self.session.get(RescheduleRequest, reschedule_request_id)
            if not resched_req:
                raise ResourceNotFoundError(f"RescheduleRequest {reschedule_request_id} not found")

            if resched_req.status != "pending":
                raise InvalidStateTransitionError(
                    f"RescheduleRequest {reschedule_request_id} is in status '{resched_req.status}', cannot reject."
                )

            resched_req.status = "rejected"
            resched_req.rejection_reason = rejection_reason
            resched_req.reviewed_by = operator_id

            # Revert ServiceRequest to scheduled if active appointment exists
            sr = self.service_request_repo.get_by_id(resched_req.service_request_id)
            if sr:
                active_appt = (
                    self.session.query(Appointment)
                    .filter(Appointment.service_request_id == sr.id, Appointment.status.in_(["scheduled", "confirmed"]))
                    .first()
                )
                if active_appt:
                    sr.status = "scheduled"

            self.audit_log_repo.create(
                entity_type="reschedule_request",
                entity_id=str(resched_req.id),
                action="reschedule_request.rejected",
                details={
                    "operator_id": operator_id,
                    "rejection_reason": rejection_reason,
                },
            )

            logger.info("RescheduleRequest %s rejected by operator %s", resched_req.id, operator_id)
            return resched_req

    # --------------------------------------------------------------------------
    # 8. Reassign Technician
    # --------------------------------------------------------------------------

    def reassign_technician(
        self,
        appointment_id: int,
        new_technician_id: Optional[int] = None,
        reason: Optional[str] = None,
        actor_type: str = "operator",
        actor_id: Optional[str] = None,
    ) -> Appointment:
        """Reassign an appointment to a new technician."""
        tx_context = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        with tx_context:
            appointment = self.appointment_repo.get_by_id(appointment_id)
            if not appointment:
                raise ResourceNotFoundError(f"Appointment {appointment_id} not found")

            if appointment.status in ["completed", "cancelled", "in_progress"]:
                raise InvalidStateTransitionError(
                    f"Cannot reassign technician for appointment with status '{appointment.status}'."
                )

            target_tech_id: Optional[int] = new_technician_id
            if target_tech_id is None:
                # Auto-find candidate technician who is active and not current technician
                candidates = (
                    self.session.query(Technician)
                    .filter(Technician.status == "active", Technician.id != appointment.technician_id)
                    .all()
                )
                if not candidates:
                    raise ReassignmentNoCandidateError(
                        "No available alternative technician found for reassignment."
                    )
                target_tech_id = candidates[0].id

            # Verify target technician exists and is active
            target_tech = self.session.get(Technician, target_tech_id)
            if not target_tech or target_tech.status != "active":
                raise ReassignmentNoCandidateError(
                    f"Technician {target_tech_id} is not found or not active."
                )

            old_tech_id = appointment.technician_id
            appointment.technician_id = target_tech_id

            # Audit Log
            self.audit_log_repo.create(
                entity_type="appointment",
                entity_id=str(appointment.id),
                action="appointment.reassigned",
                details={
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                    "old_technician_id": old_tech_id,
                    "new_technician_id": target_tech_id,
                    "reason": reason,
                },
            )

            # Outbox Event
            self.outbox_repo.create(
                event_type="appointment.reassigned",
                aggregate_type="appointment",
                aggregate_id=str(appointment.id),
                payload={
                    "appointment_id": appointment.id,
                    "old_technician_id": old_tech_id,
                    "new_technician_id": target_tech_id,
                    "reason": reason,
                },
            )

            try:
                REASSIGNMENTS_TOTAL.inc()
            except Exception:
                pass

            logger.info("Appointment %s reassigned from tech %s to tech %s",
                        appointment.id, old_tech_id, target_tech_id)
            return appointment
