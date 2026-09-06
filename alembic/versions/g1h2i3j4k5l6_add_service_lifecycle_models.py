"""add_service_lifecycle_models

Revision ID: g1h2i3j4k5l6
Revises: b1c2d3e4f5a6
Create Date: 2026-09-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add lifecycle columns to appointments
    with op.batch_alter_table('appointments') as batch_op:
        batch_op.add_column(sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('completion_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('resolution_summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('replaced_by_appointment_id', sa.Integer(), sa.ForeignKey('appointments.id'), nullable=True))
        batch_op.add_column(sa.Column('rescheduled_from_appointment_id', sa.Integer(), sa.ForeignKey('appointments.id'), nullable=True))

    # 2. Create reschedule_requests table
    op.create_table(
        'reschedule_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('service_request_id', sa.Integer(), sa.ForeignKey('service_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('appointment_id', sa.Integer(), sa.ForeignKey('appointments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_by_type', sa.String(length=50), nullable=False),
        sa.Column('requested_by_id', sa.String(length=100), nullable=True),
        sa.Column('preferred_time', sa.String(length=255), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('replacement_appointment_id', sa.Integer(), sa.ForeignKey('appointments.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reschedule_requests_service_request_id', 'reschedule_requests', ['service_request_id'])
    op.create_index('ix_reschedule_requests_appointment_id', 'reschedule_requests', ['appointment_id'])
    op.create_index('ix_reschedule_requests_status', 'reschedule_requests', ['status'])


def downgrade() -> None:
    op.drop_index('ix_reschedule_requests_status', table_name='reschedule_requests')
    op.drop_index('ix_reschedule_requests_appointment_id', table_name='reschedule_requests')
    op.drop_index('ix_reschedule_requests_service_request_id', table_name='reschedule_requests')
    op.drop_table('reschedule_requests')

    with op.batch_alter_table('appointments') as batch_op:
        batch_op.drop_column('rescheduled_from_appointment_id')
        batch_op.drop_column('replaced_by_appointment_id')
        batch_op.drop_column('resolution_summary')
        batch_op.drop_column('completion_notes')
        batch_op.drop_column('completed_at')
        batch_op.drop_column('started_at')
