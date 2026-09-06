"""add_outbox_and_notification_jobs

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-09-04 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notification_jobs and outbox_events tables with constraints and indexes."""
    json_type = (
        postgresql.JSON(astext_type=sa.Text())
        if op.get_bind().dialect.name == "postgresql"
        else sa.JSON()
    )

    # 1. Create notification_jobs table
    op.create_table(
        'notification_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('job_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('appointment_id', 'job_type', 'scheduled_for', name='uq_notification_jobs_appointment_job_schedule'),
    )
    op.create_index('ix_notification_jobs_appointment_id', 'notification_jobs', ['appointment_id'], unique=False)
    op.create_index('ix_notification_jobs_status', 'notification_jobs', ['status'], unique=False)

    # 2. Create outbox_events table
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('aggregate_type', sa.String(length=100), nullable=False),
        sa.Column('aggregate_id', sa.String(length=100), nullable=False),
        sa.Column('payload', json_type, nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outbox_events_event_type', 'outbox_events', ['event_type'], unique=False)
    op.create_index('ix_outbox_events_status', 'outbox_events', ['status'], unique=False)


def downgrade() -> None:
    """Drop outbox_events and notification_jobs tables."""
    op.drop_index('ix_outbox_events_status', table_name='outbox_events')
    op.drop_index('ix_outbox_events_event_type', table_name='outbox_events')
    op.drop_table('outbox_events')

    op.drop_index('ix_notification_jobs_status', table_name='notification_jobs')
    op.drop_index('ix_notification_jobs_appointment_id', table_name='notification_jobs')
    op.drop_table('notification_jobs')
