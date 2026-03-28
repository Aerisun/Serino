"""add asset scope

Revision ID: 0018_add_asset_scope
Revises: 0017_add_content_categories
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0018_add_asset_scope"
down_revision = "0017_add_content_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "assets" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("assets")}
    if "scope" not in existing_columns:
        op.add_column(
            "assets",
            sa.Column("scope", sa.String(length=32), nullable=False, server_default="user"),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "assets" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("assets")}
    if "scope" in existing_columns:
        with op.batch_alter_table("assets") as batch_op:
            batch_op.drop_column("scope")
