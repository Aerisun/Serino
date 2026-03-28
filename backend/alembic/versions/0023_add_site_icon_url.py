"""add site icon url

Revision ID: 0023_add_site_icon_url
Revises: 0022_add_site_admin_identities
Create Date: 2026-03-27 10:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0023_add_site_icon_url"
down_revision = "0022_add_site_admin_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "site_profile" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("site_profile")}
    if "site_icon_url" not in existing_columns:
        op.add_column(
            "site_profile",
            sa.Column("site_icon_url", sa.String(length=500), nullable=False, server_default=""),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "site_profile" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("site_profile")}
    if "site_icon_url" in existing_columns:
        with op.batch_alter_table("site_profile") as batch_op:
            batch_op.drop_column("site_icon_url")
