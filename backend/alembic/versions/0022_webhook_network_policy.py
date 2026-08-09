"""Add explicit private-network policy for webhook subscriptions.

Revision ID: 0022_webhook_network_policy
Revises: 0021_system_diagnostics
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0022_webhook_network_policy"
down_revision = "0021_system_diagnostics"
branch_labels = None
depends_on = None

TABLE_NAME = "webhook_subscriptions"
COLUMN_NAME = "allow_private_network"


def _columns() -> set[str]:
    inspector = inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return set()
    return {str(column["name"]) for column in inspector.get_columns(TABLE_NAME)}


def upgrade() -> None:
    if TABLE_NAME in inspect(op.get_bind()).get_table_names() and COLUMN_NAME not in _columns():
        op.add_column(
            TABLE_NAME,
            sa.Column(COLUMN_NAME, sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    if COLUMN_NAME in _columns():
        op.drop_column(TABLE_NAME, COLUMN_NAME)
