"""add site admin session and email password

Revision ID: 0048_add_site_admin_session_and_email_password
Revises: 0047_drop_unused_page_config_fields
Create Date: 2026-04-03 20:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0048_add_site_admin_session_and_email_password"
down_revision = "0047_drop_unused_page_config_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "site_auth_config" in existing_tables:
        config_columns = {column["name"] for column in inspector.get_columns("site_auth_config")}
        if "admin_email_password_hash" not in config_columns:
            op.add_column(
                "site_auth_config",
                sa.Column("admin_email_password_hash", sa.String(length=255), nullable=True),
            )
        if "admin_console_auth_methods" not in config_columns:
            op.add_column(
                "site_auth_config",
                sa.Column("admin_console_auth_methods", sa.JSON(), nullable=False, server_default="[]"),
            )
            config_table = sa.table(
                "site_auth_config",
                sa.column("id", sa.String(length=36)),
                sa.column("admin_auth_methods", sa.JSON()),
                sa.column("admin_email_enabled", sa.Boolean()),
                sa.column("admin_console_auth_methods", sa.JSON()),
            )
            rows = op.get_bind().execute(
                sa.select(
                    config_table.c.id,
                    config_table.c.admin_auth_methods,
                    config_table.c.admin_email_enabled,
                )
            ).fetchall()
            for row in rows:
                methods = list(row.admin_auth_methods or [])
                if row.admin_email_enabled and "email" not in methods:
                    methods.append("email")
                op.get_bind().execute(
                    config_table.update()
                    .where(config_table.c.id == row.id)
                    .values(admin_console_auth_methods=methods)
                )
            with op.batch_alter_table("site_auth_config", schema=None) as batch_op:
                batch_op.alter_column("admin_console_auth_methods", server_default=None)

    if "site_user_sessions" in existing_tables:
        session_columns = {column["name"] for column in inspector.get_columns("site_user_sessions")}
        if "admin_verified_provider" not in session_columns:
            op.add_column(
                "site_user_sessions",
                sa.Column("admin_verified_provider", sa.String(length=40), nullable=True),
            )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "site_user_sessions" in existing_tables:
        session_columns = {column["name"] for column in inspector.get_columns("site_user_sessions")}
        if "admin_verified_provider" in session_columns:
            with op.batch_alter_table("site_user_sessions", schema=None) as batch_op:
                batch_op.drop_column("admin_verified_provider")

    if "site_auth_config" in existing_tables:
        config_columns = {column["name"] for column in inspector.get_columns("site_auth_config")}
        if "admin_console_auth_methods" in config_columns:
            with op.batch_alter_table("site_auth_config", schema=None) as batch_op:
                batch_op.drop_column("admin_console_auth_methods")
        if "admin_email_password_hash" in config_columns:
            with op.batch_alter_table("site_auth_config", schema=None) as batch_op:
                batch_op.drop_column("admin_email_password_hash")
