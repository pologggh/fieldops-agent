from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from fieldops.db.models import Technician


class TechnicianRepository:
    """Repository for Technician data access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, technician_id: int, load_skills: bool = False) -> Technician | None:
        """Find a technician by primary key ID, optionally eagerly loading skills."""
        stmt = select(Technician).where(Technician.id == technician_id)
        if load_skills:
            stmt = stmt.options(selectinload(Technician.skills))
        return self.session.scalar(stmt)

    def list_active(self, load_skills: bool = False) -> list[Technician]:
        """List all technicians with active status."""
        stmt = select(Technician).where(Technician.status == "active")
        if load_skills:
            stmt = stmt.options(selectinload(Technician.skills))
        return list(self.session.scalars(stmt).all())

    def find_by_service_area(
        self, service_area: str, active_only: bool = True, load_skills: bool = False
    ) -> list[Technician]:
        """Find technicians stationed in a specific service area."""
        stmt = select(Technician).where(Technician.service_area == service_area)
        if active_only:
            stmt = stmt.where(Technician.status == "active")
        if load_skills:
            stmt = stmt.options(selectinload(Technician.skills))
        return list(self.session.scalars(stmt).all())

    def find_active_by_area_with_skills(self, service_area: str) -> list[Technician]:
        """Find active technicians in a service area with skills eagerly loaded.

        Performs case-insensitive, whitespace-trimmed comparison on service_area.
        """
        stmt = (
            select(Technician)
            .where(
                func.lower(Technician.service_area) == func.lower(service_area.strip()),
                Technician.status == "active",
            )
            .options(selectinload(Technician.skills))
        )
        return list(self.session.scalars(stmt).all())

    def create(
        self, name: str, service_area: str, status: str = "active"
    ) -> Technician:
        """Create and persist a new technician."""
        technician = Technician(
            name=name,
            service_area=service_area,
            status=status,
        )
        self.session.add(technician)
        self.session.flush()
        return technician
