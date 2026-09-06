"""add_admin_console_tables

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-04 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. internal_users
    op.create_table(
        'internal_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_internal_users_email', 'internal_users', ['email'], unique=True)

    # 2. Add capacity & emergency columns to technicians if not exists
    with op.batch_alter_table('technicians') as batch_op:
        batch_op.add_column(sa.Column('max_daily_work_minutes', sa.Integer(), server_default='480', nullable=False))
        batch_op.add_column(sa.Column('max_daily_jobs', sa.Integer(), server_default='5', nullable=True))
        batch_op.add_column(sa.Column('is_available_for_emergency', sa.Boolean(), server_default='0', nullable=False))

    # 3. dispatch_policies
    op.create_table(
        'dispatch_policies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('weights', sa.JSON(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dispatch_policies_version', 'dispatch_policies', ['version'], unique=True)
    op.create_index('ix_dispatch_policies_is_active', 'dispatch_policies', ['is_active'])

    # 4. sla_policies
    op.create_table(
        'sla_policies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('targets', sa.JSON(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sla_policies_version', 'sla_policies', ['version'], unique=True)
    op.create_index('ix_sla_policies_is_active', 'sla_policies', ['is_active'])


def downgrade() -> None:
    op.drop_table('sla_policies')
    op.drop_table('dispatch_policies')
    with op.batch_alter_table('technicians') as batch_op:
        batch_op.drop_column('is_available_for_emergency')
        batch_op.drop_column('max_daily_jobs')
        batch_op.drop_column('max_daily_work_minutes')
    op.drop_index('ix_internal_users_email', table_name='internal_users')
    op.drop_table('internal_users')
