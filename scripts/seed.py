"""Seed data script for FieldOps Agent database."""

from datetime import datetime, time, timedelta
from pathlib import Path
import sys
from typing import Sequence
from zoneinfo import ZoneInfo

# Ensure 'src' is available in sys.path when running as a standalone script
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.core.config import settings
from fieldops.db.models import (
    Appointment,
    Customer,
    ServiceRequest,
    Technician,
    TechnicianSkill,
)
from fieldops.db.session import SessionLocal

CUSTOMERS_SEED_DATA = [
    {"name": "Alice", "email": "alice@example.com", "phone": "090-1111-2222"},
    {"name": "Bob", "email": "bob@example.com", "phone": "090-3333-4444"},
]

TECHNICIANS_SEED_DATA = [
    {
        "name": "Ken Tanaka",
        "service_area": "Shinjuku",
        "status": "active",
        "skills": ["HVAC"],
    },
    {
        "name": "Yuki Sato",
        "service_area": "Shinjuku",
        "status": "active",
        "skills": ["Plumbing"],
    },
    {
        "name": "Haru Suzuki",
        "service_area": "Yokohama",
        "status": "active",
        "skills": ["HVAC", "Electrical"],
    },
]


def seed_customers(session: Session) -> int:
    """Seed customer data idempotently."""
    created_count = 0
    for data in CUSTOMERS_SEED_DATA:
        existing = session.scalar(
            select(Customer).where(Customer.email == data["email"])
        )
        if existing is None:
            customer = Customer(
                name=data["name"],
                email=data["email"],
                phone=data.get("phone"),
            )
            session.add(customer)
            created_count += 1
            print(f"[Customer] Created: {data['name']} <{data['email']}>")
        else:
            print(f"[Customer] Already exists: {data['name']} <{data['email']}>")
    session.flush()
    return created_count


def seed_technicians(session: Session) -> int:
    """Seed technician data along with their skills idempotently."""
    created_count = 0
    for data in TECHNICIANS_SEED_DATA:
        existing_tech = session.scalar(
            select(Technician).where(Technician.name == data["name"])
        )
        if existing_tech is None:
            tech = Technician(
                name=data["name"],
                service_area=data["service_area"],
                status=data["status"],
            )
            session.add(tech)
            session.flush()

            for skill_name in data["skills"]:
                session.add(
                    TechnicianSkill(technician_id=tech.id, skill=skill_name)
                )
            created_count += 1
            print(
                f"[Technician] Created: {data['name']} in {data['service_area']} with skills {data['skills']}"
            )
        else:
            # Check for any missing skills and insert them idempotently
            existing_skills = set(
                session.scalars(
                    select(TechnicianSkill.skill).where(
                        TechnicianSkill.technician_id == existing_tech.id
                    )
                ).all()
            )
            for skill_name in data["skills"]:
                if skill_name not in existing_skills:
                    session.add(
                        TechnicianSkill(
                            technician_id=existing_tech.id, skill=skill_name
                        )
                    )
                    print(
                        f"[TechnicianSkill] Added missing skill '{skill_name}' to {data['name']}"
                    )
            print(f"[Technician] Already exists: {data['name']}")
    session.flush()
    return created_count


def seed_appointments(session: Session) -> int:
    """Seed sample appointment data idempotently for scheduling verification.

    Seeds:
        Ken Tanaka: tomorrow 13:00 - 15:00 (status: scheduled)
    """
    tz = ZoneInfo(settings.BUSINESS_TIMEZONE)
    tomorrow_date = (datetime.now(tz) + timedelta(days=1)).date()
    start_dt = datetime.combine(tomorrow_date, time(13, 0), tzinfo=tz)
    end_dt = datetime.combine(tomorrow_date, time(15, 0), tzinfo=tz)

    ken = session.scalar(select(Technician).where(Technician.name == "Ken Tanaka"))
    if ken is None:
        return 0

    alice = session.scalar(
        select(Customer).where(Customer.email == "alice@example.com")
    )
    if alice is None:
        return 0

    sr = session.scalar(
        select(ServiceRequest).where(
            ServiceRequest.customer_id == alice.id,
            ServiceRequest.service_type == "HVAC",
        )
    )
    if sr is None:
        sr = ServiceRequest(
            customer_id=alice.id,
            raw_message="Seed AC repair for appointment testing",
            service_type="HVAC",
            urgency="high",
            location="Shinjuku",
            status="scheduled",
        )
        session.add(sr)
        session.flush()

    existing_appt = session.scalar(
        select(Appointment).where(
            Appointment.technician_id == ken.id,
            Appointment.start_time == start_dt,
            Appointment.end_time == end_dt,
        )
    )
    if existing_appt is None:
        appt = Appointment(
            service_request_id=sr.id,
            technician_id=ken.id,
            start_time=start_dt,
            end_time=end_dt,
            status="scheduled",
        )
        session.add(appt)
        session.flush()
        print(
            f"[Appointment] Created: Ken Tanaka on {tomorrow_date} 13:00 - 15:00 (scheduled)"
        )
        return 1

    print(
        f"[Appointment] Already exists for Ken Tanaka on {tomorrow_date} 13:00 - 15:00"
    )
    return 0


def run_seed(session: Session) -> None:
    """Run full idempotent database seeding."""
    print("Starting database seeding...")
    customers_added = seed_customers(session)
    technicians_added = seed_technicians(session)
    appointments_added = seed_appointments(session)
    session.commit()
    print(
        f"Seeding completed successfully! (Added {customers_added} customers, {technicians_added} technicians, {appointments_added} appointments)"
    )


def main() -> None:
    """Main entrypoint for script execution."""
    with SessionLocal() as session:
        try:
            run_seed(session)
        except Exception as e:
            session.rollback()
            print(f"Error during seeding: {e}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
