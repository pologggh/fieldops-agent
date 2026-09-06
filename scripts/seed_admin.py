import bcrypt
from datetime import datetime, timezone
from fieldops.db.session import SessionLocal
from fieldops.db.models import InternalUser, DispatchPolicy, SLAPolicy

def hash_pwd(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

with SessionLocal() as session:
    users_to_seed = [
        {"email": "admin@fieldops.com", "name": "Admin User", "role": "admin", "password": "password123"},
        {"email": "operator@fieldops.com", "name": "Senior Dispatcher", "role": "operator", "password": "password123"},
        {"email": "viewer@fieldops.com", "name": "Auditor / Viewer", "role": "viewer", "password": "password123"},
    ]
    for u in users_to_seed:
        existing = session.query(InternalUser).filter_by(email=u["email"]).first()
        if not existing:
            user = InternalUser(
                email=u["email"],
                name=u["name"],
                role=u["role"],
                password_hash=hash_pwd(u["password"]),
                is_active=True,
            )
            session.add(user)
            print(f"Seeded user: {u['email']} ({u['role']})")
    
    existing_dispatch = session.query(DispatchPolicy).filter_by(version=1).first()
    if not existing_dispatch:
        default_weights = {
            "workload_weight": 25,
            "capacity_weight": 20,
            "sla_weight": 30,
            "travel_weight": 15,
            "overtime_penalty": 10,
        }
        dispatch_policy = DispatchPolicy(
            version=1,
            is_active=True,
            weights=default_weights,
            description="Default Production Dispatch Policy",
            created_by="system_seed",
        )
        session.add(dispatch_policy)
        print("Seeded DispatchPolicy version 1")

    existing_sla = session.query(SLAPolicy).filter_by(version=1).first()
    if not existing_sla:
        default_sla = {
            "P0": {"response_minutes": 15, "assignment_minutes": 30, "service_start_minutes": 120, "at_risk_threshold_minutes": 15},
            "P1": {"response_minutes": 30, "assignment_minutes": 60, "service_start_minutes": 240, "at_risk_threshold_minutes": 30},
            "P2": {"response_minutes": 60, "assignment_minutes": 120, "service_start_minutes": 480, "at_risk_threshold_minutes": 60},
            "P3": {"response_minutes": 120, "assignment_minutes": 240, "service_start_minutes": 1440, "at_risk_threshold_minutes": 120},
        }
        sla_policy = SLAPolicy(
            version=1,
            is_active=True,
            targets=default_sla,
            description="Standard Enterprise SLA Policy",
            created_by="system_seed",
        )
        session.add(sla_policy)
        print("Seeded SLAPolicy version 1")

    session.commit()
    print("Seed complete.")
