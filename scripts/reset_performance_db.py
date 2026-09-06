"""Database reset and initialization utility for performance testing.

Safety rules:
- Prohibited in production (APP_ENV == "production").
- Truncates/resets performance database tables and executes seed data script.
"""

import sys
from sqlalchemy import text

from fieldops.core.config import settings
from fieldops.db.session import engine
from scripts.seed import seed_database


def reset_performance_database() -> None:
    if settings.APP_ENV == "production":
        print("ERROR: reset_performance_db cannot be executed in production environment!", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Resetting performance database: {settings.DATABASE_URL}")
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        # Clean existing business and state tables safely in reverse dependency order
        tables = [
            "audit_logs",
            "integration_records",
            "notification_jobs",
            "outbox_events",
            "appointments",
            "service_requests",
            "inbound_events",
            "idempotency_records",
            "technician_skills",
            "technicians",
            "customers",
        ]
        for t in tables:
            try:
                conn.execute(text(f"TRUNCATE TABLE {t} CASCADE;"))
                print(f"    - Truncated table {t}")
            except Exception as e:
                # Table might not exist yet if alembic hasn't run
                print(f"    - Notice: Truncate {t} skipped ({e})")

    print("[*] Re-seeding baseline technicians and customers...")
    seed_database()
    print("[+] Performance database reset and seeded successfully.")


if __name__ == "__main__":
    reset_performance_database()
