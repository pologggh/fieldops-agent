"""add_appointment_exclusion_constraint

Revision ID: b2c3d4e5f6a1
Revises: ea72196ed2c2
Create Date: 2026-09-04 14:03:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, Sequence[str], None] = 'ea72196ed2c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with btree_gist extension and partial exclusion constraint on PostgreSQL."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # 1. Enable btree_gist extension for scalar + range exclusion index
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")

        # 2. Add partial exclusion constraint to prevent overlapping blocking appointments for the same technician
        op.execute("""
            ALTER TABLE appointments
            ADD CONSTRAINT exclude_overlapping_appointments
            EXCLUDE USING gist (
                technician_id WITH =,
                tstzrange(start_time, end_time) WITH &&
            )
            WHERE (status IN ('scheduled', 'confirmed', 'in_progress'));
        """)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS exclude_overlapping_appointments;")
