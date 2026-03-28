"""add site admin identities

Revision ID: 0022_add_site_admin_identities
Revises: 0021_add_site_auth_config
Create Date: 2026-03-26 21:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0022_add_site_admin_identities"
down_revision = "0021_add_site_auth_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "site_auth_config" in existing_tables:
        config_columns = {column["name"] for column in inspector.get_columns("site_auth_config")}
        if "admin_email_enabled" not in config_columns:
            op.add_column(
                "site_auth_config",
                sa.Column(
                    "admin_email_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )

    if "site_admin_identities" not in existing_tables:
        op.create_table(
            "site_admin_identities",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("site_user_id", sa.String(length=36), nullable=False),
            sa.Column("admin_user_id", sa.String(length=36), nullable=True),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("identifier", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("provider_display_name", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["site_user_id"], ["site_users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "identifier", name="uq_site_admin_identity_provider_identifier"),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "site_admin_identities" in existing_tables:
        op.drop_table("site_admin_identities")
    if "site_auth_config" in existing_tables:
        config_columns = {column["name"] for column in inspector.get_columns("site_auth_config")}
        if "admin_email_enabled" in config_columns:
            with op.batch_alter_table("site_auth_config", schema=None) as batch_op:
                batch_op.drop_column("admin_email_enabled")
