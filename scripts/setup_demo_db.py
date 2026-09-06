"""Setup local demo SQLite database with complete test records across all roles."""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import bcrypt
from fieldops.core.config import settings
from fieldops.db.session import Base, engine, SessionLocal
import fieldops.db.models as models

def hash_pwd(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def main():
    print(f"Creating all database tables using engine: {engine.url} ...")
    Base.metadata.create_all(engine)
    print("Tables created successfully.")

    with SessionLocal() as session:
        # 1. Internal Users
        internal_users = [
            {"email": "admin@fieldops.com", "name": "Admin User", "role": "admin", "password": "password123"},
            {"email": "operator@fieldops.com", "name": "Senior Dispatcher", "role": "operator", "password": "password123"},
            {"email": "viewer@fieldops.com", "name": "Auditor / Viewer", "role": "viewer", "password": "password123"},
        ]
        for u in internal_users:
            if not session.query(models.InternalUser).filter_by(email=u["email"]).first():
                user = models.InternalUser(
                    email=u["email"],
                    name=u["name"],
                    role=u["role"],
                    password_hash=hash_pwd(u["password"]),
                    is_active=True,
                )
                session.add(user)
                print(f"Added Internal User: {u['email']} ({u['role']})")

        # 2. Customers and Customer Accounts
        customers = [
            {
                "name": "Alice Smith",
                "email": "alice.test@example.com",
                "phone": "090-1234-5678",
                "password": "password123",
            },
            {
                "name": "Bob Johnson",
                "email": "bob@example.com",
                "phone": "090-8765-4321",
                "password": "password123",
            },
        ]
        seeded_customers = {}
        for c in customers:
            existing_c = session.query(models.Customer).filter_by(email=c["email"]).first()
            if not existing_c:
                cust = models.Customer(
                    name=c["name"],
                    email=c["email"],
                    phone=c["phone"],
                )
                session.add(cust)
                session.flush()
                account = models.CustomerAccount(
                    customer_id=cust.id,
                    email=c["email"],
                    password_hash=hash_pwd(c["password"]),
                    is_active=True,
                )
                session.add(account)
                session.flush()
                seeded_customers[c["email"]] = cust
                print(f"Added Customer: {c['name']} ({c['email']})")
            else:
                seeded_customers[c["email"]] = existing_c

        # 3. Technicians & Skills
        technicians_data = [
            {
                "name": "Ken Tanaka",
                "service_area": "Shinjuku",
                "status": "active",
                "skills": ["HVAC", "Heating"],
            },
            {
                "name": "Yuki Sato",
                "service_area": "Shinjuku",
                "status": "active",
                "skills": ["Plumbing", "Water Leak"],
            },
            {
                "name": "Haru Suzuki",
                "service_area": "Yokohama",
                "status": "active",
                "skills": ["HVAC", "Electrical"],
            },
            {
                "name": "Daiki Takahashi",
                "service_area": "Shibuya",
                "status": "active",
                "skills": ["Appliances", "Plumbing"],
            },
        ]
        seeded_techs = []
        for t in technicians_data:
            existing_t = session.query(models.Technician).filter_by(name=t["name"]).first()
            if not existing_t:
                tech = models.Technician(
                    name=t["name"],
                    service_area=t["service_area"],
                    status=t["status"],
                )
                session.add(tech)
                session.flush()
                for skill_name in t["skills"]:
                    ts = models.TechnicianSkill(
                        technician_id=tech.id,
                        skill=skill_name,
                    )
                    session.add(ts)
                seeded_techs.append(tech)
                print(f"Added Technician: {t['name']} - {t['skills']}")
            else:
                seeded_techs.append(existing_t)

        # 4. Policies
        if not session.query(models.DispatchPolicy).filter_by(version=1).first():
            dispatch_policy = models.DispatchPolicy(
                version=1,
                is_active=True,
                weights={
                    "workload_weight": 25,
                    "capacity_weight": 20,
                    "sla_weight": 30,
                    "travel_weight": 15,
                    "overtime_penalty": 10,
                },
                description="Standard Multi-factor Dispatch Policy",
                created_by="system",
            )
            session.add(dispatch_policy)
            print("Added Default DispatchPolicy v1")

        if not session.query(models.SLAPolicy).filter_by(version=1).first():
            sla_policy = models.SLAPolicy(
                version=1,
                is_active=True,
                targets={
                    "P0": {"response_minutes": 15, "assignment_minutes": 30, "service_start_minutes": 120, "at_risk_threshold_minutes": 15},
                    "P1": {"response_minutes": 30, "assignment_minutes": 60, "service_start_minutes": 240, "at_risk_threshold_minutes": 30},
                    "P2": {"response_minutes": 60, "assignment_minutes": 120, "service_start_minutes": 480, "at_risk_threshold_minutes": 60},
                    "P3": {"response_minutes": 120, "assignment_minutes": 240, "service_start_minutes": 1440, "at_risk_threshold_minutes": 120},
                },
                description="Standard Enterprise SLA Targets",
                created_by="system",
            )
            session.add(sla_policy)
            print("Added Default SLAPolicy v1")

        # 5. Sample Service Requests & Appointments for Alice
        alice = seeded_customers.get("alice.test@example.com")
        if alice and session.query(models.ServiceRequest).count() == 0:
            now = datetime.now(timezone.utc)

            # Request 1: Active scheduled request
            sr1 = models.ServiceRequest(
                customer_id=alice.id,
                raw_message="Kitchen Water Heater Repair: Water heater leaking from underneath rapidly, making buzzing sound.",
                service_type="Plumbing",
                urgency="high",
                status="scheduled",
                location="Shinjuku-ku, Nishi-Shinjuku 2-8-1, Tokyo",
                sla_deadline=now + timedelta(hours=4),
                created_at=now - timedelta(hours=2),
            )
            session.add(sr1)
            session.flush()

            # Appointment for Request 1
            appt1 = models.Appointment(
                service_request_id=sr1.id,
                technician_id=seeded_techs[1].id,
                status="scheduled",
                start_time=now + timedelta(days=1, hours=2),
                end_time=now + timedelta(days=1, hours=4),
            )
            session.add(appt1)

            # Request 2: Needs attention / waiting for approval
            sr2 = models.ServiceRequest(
                customer_id=alice.id,
                raw_message="HVAC Air Conditioner AC-300 Not Cooling: AC blowing warm air, error code E4 displayed on the thermostat.",
                service_type="HVAC",
                urgency="critical",
                status="waiting_for_approval",
                location="Shinjuku-ku, Nishi-Shinjuku 2-8-1, Tokyo",
                sla_deadline=now + timedelta(minutes=15),
                created_at=now - timedelta(minutes=45),
            )
            session.add(sr2)

            # Request 3: Routine inspection
            sr3 = models.ServiceRequest(
                customer_id=alice.id,
                raw_message="Annual Electrical Panel Inspection: Regular safety audit of main distribution board.",
                service_type="Electrical",
                urgency="routine",
                status="ready_for_review",
                location="Shinjuku-ku, Nishi-Shinjuku 2-8-1, Tokyo",
                sla_deadline=now + timedelta(days=2),
                created_at=now - timedelta(days=1),
            )
            session.add(sr3)

            # Audit Log
            audit = models.AuditLog(
                entity_type="service_request",
                entity_id=str(sr1.id),
                action="schedule_confirmed",
                details={
                    "technician_id": seeded_techs[1].id,
                    "duration": 120,
                    "summary": f"Appointment #{appt1.id} confirmed with technician Yuki Sato",
                    "actor": "Senior Dispatcher",
                    "actor_type": "internal_user",
                },
            )
            session.add(audit)
            print("Created rich demo ServiceRequests and Appointment.")

        session.commit()
        print("Demo database initialization completed successfully!")

if __name__ == "__main__":
    main()
