"""Drop legacy admin email password hash.

Revision ID: 0004_drop_admin_email_password_hash
Revises: 0003_comment_image_rate_limit
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004_drop_admin_email_password_hash"
down_revision = "0003_comment_image_rate_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("site_auth_config")}
    if "admin_email_password_hash" in existing_columns:
        op.drop_column("site_auth_config", "admin_email_password_hash")


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("site_auth_config")}
    if "admin_email_password_hash" not in existing_columns:
        op.add_column(
            "site_auth_config",
            sa.Column("admin_email_password_hash", sa.String(length=255), nullable=True),
        )
