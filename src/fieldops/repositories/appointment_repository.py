from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.db.models import Appointment

BLOCKING_APPOINTMENT_STATUSES = ("scheduled", "confirmed", "in_progress")


class AppointmentRepository:
    """Repository for Appointment database queries and persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, appointment_id: int) -> Appointment | None:
        """Find an appointment by its primary key ID."""
        return self.session.get(Appointment, appointment_id)

    def get_blocking_by_technician_and_window(
        self,
        technician_id: int,
        window_start: datetime,
        window_end: datetime,
    ) -> list[Appointment]:
        """Query active appointments that overlap with the specified window.

        Overlap condition:
            existing.start_time < window_end AND existing.end_time > window_start
        Filtering:
            Only appointments with blocking status ('scheduled', 'confirmed', 'in_progress').
            Non-blocking statuses ('cancelled', 'rejected') are excluded.
        """
        stmt = (
            select(Appointment)
            .where(
                Appointment.technician_id == technician_id,
                Appointment.status.in_(BLOCKING_APPOINTMENT_STATUSES),
                Appointment.start_time < window_end,
                Appointment.end_time > window_start,
            )
            .order_by(Appointment.start_time.asc())
        )
        return list(self.session.scalars(stmt).all())

    def create(
        self,
        service_request_id: int,
        technician_id: int,
        start_time: datetime,
        end_time: datetime,
        status: str = "scheduled",
    ) -> Appointment:
        """Create and flush a new Appointment record into the database session."""
        appointment = Appointment(
            service_request_id=service_request_id,
            technician_id=technician_id,
            start_time=start_time,
            end_time=end_time,
            status=status,
        )
        self.session.add(appointment)
        self.session.flush()
        return appointment

    def get_by_service_request_id(
        self, service_request_id: int
    ) -> Appointment | None:
        """Find an existing appointment associated with a service request."""
        stmt = (
            select(Appointment)
            .where(Appointment.service_request_id == service_request_id)
            .order_by(Appointment.id.desc())
        )
        return self.session.scalars(stmt).first()
