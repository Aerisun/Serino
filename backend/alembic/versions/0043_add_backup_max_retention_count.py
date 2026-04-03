"""Add max_retention_count to backup_target_configs.

Allows operators to set a maximum number of backup commits to retain.
When set to 0 (default), retention is unlimited.

Revision ID: 0043_add_backup_max_retention_count
Revises: 0042_drop_dead_community_config_columns
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0043_add_backup_max_retention_count"
down_revision = "0042_drop_dead_community_config_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {col["name"] for col in inspector.get_columns("backup_target_configs")}
    if "max_retention_count" not in columns:
        op.add_column(
            "backup_target_configs",
            sa.Column("max_retention_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {col["name"] for col in inspector.get_columns("backup_target_configs")}
    if "max_retention_count" in columns:
        op.drop_column("backup_target_configs", "max_retention_count")
