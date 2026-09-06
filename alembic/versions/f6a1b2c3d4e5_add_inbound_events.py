"""add_inbound_events

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-09-04 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e5f6a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inbound_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('external_message_id', sa.String(length=255), nullable=True),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='received', nullable=False),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('service_request_id', sa.Integer(), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'external_message_id', name='uq_inbound_events_source_msg_id'),
    )
    op.create_index('ix_inbound_events_source', 'inbound_events', ['source'], unique=False)
    op.create_index('ix_inbound_events_external_message_id', 'inbound_events', ['external_message_id'], unique=False)
    op.create_index('ix_inbound_events_status', 'inbound_events', ['status'], unique=False)
    op.create_index('ix_inbound_events_request_id', 'inbound_events', ['request_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_inbound_events_request_id', table_name='inbound_events')
    op.drop_index('ix_inbound_events_status', table_name='inbound_events')
    op.drop_index('ix_inbound_events_external_message_id', table_name='inbound_events')
    op.drop_index('ix_inbound_events_source', table_name='inbound_events')
    op.drop_table('inbound_events')
