"""Remove content status fields.

Revision ID: 0005_remove_content_status
Revises: 0004_drop_admin_email_password_hash
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0005_remove_content_status"
down_revision = "0004_drop_admin_email_password_hash"
branch_labels = None
depends_on = None


CONTENT_TABLES = ("posts", "diary_entries", "thoughts", "excerpts")


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in CONTENT_TABLES:
        existing_columns = _columns(table_name)
        if "status" in existing_columns and "visibility" in existing_columns:
            bind.execute(
                text(f"UPDATE {table_name} SET visibility = 'private' WHERE status IN ('draft', 'archived')")
            )
            bind.execute(
                text(
                    f"UPDATE {table_name} "
                    "SET visibility = 'public' "
                    "WHERE status = 'published' AND visibility NOT IN ('public', 'private')"
                )
            )
        if "status" in existing_columns:
            op.drop_column(table_name, "status")
        if "first_archived_at" in existing_columns:
            op.drop_column(table_name, "first_archived_at")


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(CONTENT_TABLES):
        existing_columns = _columns(table_name)
        if "first_archived_at" not in existing_columns:
            op.add_column(table_name, sa.Column("first_archived_at", sa.DateTime(timezone=True), nullable=True))
        existing_columns = _columns(table_name)
        if "status" not in existing_columns:
            op.add_column(
                table_name,
                sa.Column("status", sa.String(length=32), nullable=False, server_default="published"),
            )
            bind.execute(
                text(
                    f"UPDATE {table_name} "
                    "SET status = CASE WHEN visibility = 'public' THEN 'published' ELSE 'archived' END"
                )
            )
