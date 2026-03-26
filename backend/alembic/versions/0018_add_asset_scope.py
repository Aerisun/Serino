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

    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(
            sa.Column("scope", sa.String(length=32), nullable=False, server_default="user")
        )

    with op.batch_alter_table("assets") as batch_op:
        batch_op.alter_column("scope", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_column("scope")