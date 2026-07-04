"""Add content notification failure attempts.

Revision ID: 0011_content_notification_failed_attempts
Revises: 0010_diary_access_requests
Create Date: 2026-07-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0011_content_notification_failed_attempts"
down_revision = "0010_diary_access_requests"
branch_labels = None
depends_on = None

TABLE = "content_notifications"
COLUMN = "failed_attempts"


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns() -> set[str]:
    if TABLE not in _table_names():
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if COLUMN not in _columns():
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if COLUMN in _columns():
        op.drop_column(TABLE, COLUMN)
