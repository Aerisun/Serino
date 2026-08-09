"""Persist the authorization principal used by Agent runs.

Revision ID: 0023_agent_run_principal
Revises: 0022_webhook_network_policy
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0023_agent_run_principal"
down_revision = "0022_webhook_network_policy"
branch_labels = None
depends_on = None

TABLE_NAME = "agent_runs"
COLUMNS = {
    "requested_by_type": sa.Column(
        "requested_by_type",
        sa.String(length=40),
        nullable=False,
        server_default="system",
    ),
    "requested_by_id": sa.Column("requested_by_id", sa.String(length=120), nullable=True),
    "authorization_scopes": sa.Column(
        "authorization_scopes",
        sa.JSON(),
        nullable=False,
        server_default='["*"]',
    ),
}


def _column_names() -> set[str]:
    inspector = inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return set()
    return {str(column["name"]) for column in inspector.get_columns(TABLE_NAME)}


def upgrade() -> None:
    existing = _column_names()
    for name, column in COLUMNS.items():
        if name not in existing:
            op.add_column(TABLE_NAME, column)


def downgrade() -> None:
    existing = _column_names()
    for name in reversed(tuple(COLUMNS)):
        if name in existing:
            op.drop_column(TABLE_NAME, name)
