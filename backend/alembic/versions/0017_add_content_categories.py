"""add content categories

Revision ID: 0017_add_content_categories
Revises: 0016_add_hero_image_fields
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0017_add_content_categories"
down_revision = "0016_add_hero_image_fields"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    if "content_categories" not in inspector.get_table_names():
        op.create_table(
            "content_categories",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("content_type", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("content_type", "name", name="uq_content_categories_type_name"),
        )
        op.create_index(
            "ix_content_categories_content_type",
            "content_categories",
            ["content_type"],
            unique=False,
        )

    for table_name in ("diary_entries", "thoughts", "excerpts"):
        if table_name in inspector.get_table_names() and not _has_column(inspector, table_name, "category"):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column("category", sa.String(length=80), nullable=True))


def downgrade() -> None:
    for table_name in ("excerpts", "thoughts", "diary_entries"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column("category")

    op.drop_index("ix_content_categories_content_type", table_name="content_categories")
    op.drop_table("content_categories")
