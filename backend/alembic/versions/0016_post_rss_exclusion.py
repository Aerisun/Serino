"""Add the post RSS exclusion flag.

Revision ID: 0016_post_rss_exclusion
Revises: 0015_diary_access_latest_request_index
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0016_post_rss_exclusion"
down_revision = "0015_diary_access_latest_request_index"
branch_labels = None
depends_on = None

TABLE = "posts"
COLUMN = "exclude_from_rss"


def _column_names() -> set[str]:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return set()
    return {column["name"] for column in inspect(bind).get_columns(TABLE)}


def upgrade() -> None:
    if COLUMN not in _column_names():
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    if COLUMN in _column_names():
        op.drop_column(TABLE, COLUMN)
