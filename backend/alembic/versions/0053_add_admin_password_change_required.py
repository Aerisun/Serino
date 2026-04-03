"""Add password change required flag to admin users.

Revision ID: 0053_add_admin_password_change_required
Revises: 0052_add_data_migration_tracking
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0053_add_admin_password_change_required"
down_revision = "0052_add_data_migration_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "admin_users" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("admin_users")}
    if "password_change_required" not in columns:
        op.add_column(
            "admin_users",
            sa.Column(
                "password_change_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "admin_users" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("admin_users")}
    if "password_change_required" in columns:
        op.drop_column("admin_users", "password_change_required")
