"""Add stable public title identity fields.

Revision ID: 0002_public_title_identity
Revises: 0001_production_baseline
Create Date: 2026-04-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002_public_title_identity"
down_revision = "0001_production_baseline"
branch_labels = None
depends_on = None


CONTENT_TABLES = ("posts", "diary_entries", "thoughts", "excerpts")


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    for table_name in CONTENT_TABLES:
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "public_title" not in existing_columns:
            op.add_column(table_name, sa.Column("public_title", sa.String(length=240), nullable=True))
        if "first_published_at" not in existing_columns:
            op.add_column(table_name, sa.Column("first_published_at", sa.DateTime(timezone=True), nullable=True))
        if "first_archived_at" not in existing_columns:
            op.add_column(table_name, sa.Column("first_archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    for table_name in reversed(CONTENT_TABLES):
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "first_archived_at" in existing_columns:
            op.drop_column(table_name, "first_archived_at")
        if "first_published_at" in existing_columns:
            op.drop_column(table_name, "first_published_at")
        if "public_title" in existing_columns:
            op.drop_column(table_name, "public_title")
