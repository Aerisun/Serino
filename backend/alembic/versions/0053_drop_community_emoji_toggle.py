"""Drop legacy community emoji toggle.

Revision ID: 0053_drop_community_emoji_toggle
Revises: 0052_add_data_migration_tracking
Create Date: 2026-04-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0053_drop_community_emoji_toggle"
down_revision = "0052_add_data_migration_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("community_config")}

    if "enable_enjoy_search" in columns:
        with op.batch_alter_table("community_config") as batch_op:
            batch_op.drop_column("enable_enjoy_search")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("community_config")}

    if "enable_enjoy_search" not in columns:
        with op.batch_alter_table("community_config") as batch_op:
            batch_op.add_column(
                sa.Column("enable_enjoy_search", sa.Boolean(), nullable=False, server_default=sa.true()),
            )
