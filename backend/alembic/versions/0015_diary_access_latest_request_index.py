"""Add diary access latest-request index.

Revision ID: 0015_diary_access_latest_request_index
Revises: 0014_persist_content_view_counts
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0015_diary_access_latest_request_index"
down_revision = "0014_persist_content_view_counts"
branch_labels = None
depends_on = None

TABLE = "diary_access_requests"
INDEX = "ix_diary_access_requests_site_user_created_id"
INDEX_COLUMNS = ["site_user_id", sa.text("created_at DESC"), sa.text("id DESC")]


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes() -> set[str]:
    if TABLE not in _table_names():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade() -> None:
    if TABLE in _table_names() and INDEX not in _indexes():
        op.create_index(INDEX, TABLE, INDEX_COLUMNS)


def downgrade() -> None:
    if TABLE in _table_names() and INDEX in _indexes():
        op.drop_index(INDEX, table_name=TABLE)
