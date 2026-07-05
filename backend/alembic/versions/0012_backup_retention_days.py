"""Add backup retention days.

Revision ID: 0012_backup_retention_days
Revises: 0011_content_notification_failed_attempts
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0012_backup_retention_days"
down_revision = "0011_content_notification_failed_attempts"
branch_labels = None
depends_on = None

TABLE = "backup_target_configs"
COLUMN = "retention_days"


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns() -> set[str]:
    if TABLE not in _table_names():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if TABLE not in _table_names():
        return
    if COLUMN not in _columns():
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.Integer(), nullable=False, server_default="60"),
        )
    op.execute(
        text(
            """
            UPDATE backup_target_configs
            SET interval_minutes = 1440
            WHERE interval_minutes = 60
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE backup_target_configs
            SET max_retention_count = 80
            WHERE max_retention_count = 0
            """
        )
    )


def downgrade() -> None:
    if TABLE in _table_names() and COLUMN in _columns():
        op.drop_column(TABLE, COLUMN)
