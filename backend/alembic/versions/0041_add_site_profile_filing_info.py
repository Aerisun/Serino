"""Add filing info field to site profile.

Revision ID: 0041_add_site_profile_filing_info
Revises: 0040_add_backup_recovery_keys
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0041_add_site_profile_filing_info"
down_revision = "0040_add_backup_recovery_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("site_profile")}
    if "filing_info" not in columns:
        op.add_column(
            "site_profile",
            sa.Column("filing_info", sa.String(length=255), nullable=False, server_default=""),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("site_profile")}
    if "filing_info" in columns:
        op.drop_column("site_profile", "filing_info")
