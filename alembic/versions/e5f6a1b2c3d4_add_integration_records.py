"""add_integration_records

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-09-04 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Expand notification_jobs table
    op.add_column('notification_jobs', sa.Column('provider', sa.String(length=100), nullable=True))
    op.add_column('notification_jobs', sa.Column('provider_message_id', sa.String(length=255), nullable=True))
    op.add_column('notification_jobs', sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True))

    # 2. Create integration_records table
    op.create_table(
        'integration_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('local_resource_id', sa.Integer(), nullable=False),
        sa.Column('external_resource_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'resource_type', 'local_resource_id', name='uq_integration_records_provider_resource'),
    )
    op.create_index('ix_integration_records_provider', 'integration_records', ['provider'], unique=False)
    op.create_index('ix_integration_records_local_resource_id', 'integration_records', ['local_resource_id'], unique=False)
    op.create_index('ix_integration_records_status', 'integration_records', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_integration_records_status', table_name='integration_records')
    op.drop_index('ix_integration_records_local_resource_id', table_name='integration_records')
    op.drop_index('ix_integration_records_provider', table_name='integration_records')
    op.drop_table('integration_records')

    op.drop_column('notification_jobs', 'sent_at')
    op.drop_column('notification_jobs', 'provider_message_id')
    op.drop_column('notification_jobs', 'provider')
