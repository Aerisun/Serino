"""Add visit records table

Revision ID: 0019_add_visit_records
Revises: 0018_add_asset_scope
Create Date: 2026-03-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '0019_add_visit_records'
down_revision: Union[str, None] = '0018_add_asset_scope'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table('visit_records'):
        return

    op.create_table(
        'visit_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('visited_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('path', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('referer', sa.String(length=500), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_bot', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_visit_records_visited_at', 'visit_records', ['visited_at'], unique=False)
    op.create_index('ix_visit_records_path_visited_at', 'visit_records', ['path', 'visited_at'], unique=False)
    op.create_index('ix_visit_records_ip_address_visited_at', 'visit_records', ['ip_address', 'visited_at'], unique=False)
    op.create_index('ix_visit_records_is_bot', 'visit_records', ['is_bot'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table('visit_records'):
        return

    op.drop_index('ix_visit_records_is_bot', table_name='visit_records')
    op.drop_index('ix_visit_records_ip_address_visited_at', table_name='visit_records')
    op.drop_index('ix_visit_records_path_visited_at', table_name='visit_records')
    op.drop_index('ix_visit_records_visited_at', table_name='visit_records')
    op.drop_table('visit_records')
