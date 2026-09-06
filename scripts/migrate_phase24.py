import sqlite3
import os

db_path = 'fieldops_demo.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("PRAGMA table_info(appointments)")
    cols = [row[1] for row in c.fetchall()]
    print("Current appointment cols:", cols)

    new_cols = [
        ("started_at", "DATETIME"),
        ("completed_at", "DATETIME"),
        ("completion_notes", "TEXT"),
        ("resolution_summary", "TEXT"),
        ("replaced_by_appointment_id", "INTEGER REFERENCES appointments(id)"),
        ("rescheduled_from_appointment_id", "INTEGER REFERENCES appointments(id)")
    ]

    for col_name, col_type in new_cols:
        if col_name not in cols:
            print(f"Adding {col_name} to appointments")
            c.execute(f"ALTER TABLE appointments ADD COLUMN {col_name} {col_type}")

    c.execute("""
    CREATE TABLE IF NOT EXISTS reschedule_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_request_id INTEGER NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,
        appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
        requested_by_type VARCHAR(50) NOT NULL,
        requested_by_id VARCHAR(100),
        preferred_time VARCHAR(255),
        reason TEXT,
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        reviewed_by VARCHAR(100),
        rejection_reason TEXT,
        replacement_appointment_id INTEGER REFERENCES appointments(id),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_reschedule_requests_service_request_id ON reschedule_requests(service_request_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_reschedule_requests_appointment_id ON reschedule_requests(appointment_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_reschedule_requests_status ON reschedule_requests(status)")

    conn.commit()
    conn.close()
    print("SQLite schema migration completed successfully.")
else:
    print("fieldops_demo.db not found, skipping SQLite update.")
