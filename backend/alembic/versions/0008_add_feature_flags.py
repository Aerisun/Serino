"""Add feature_flags to site_profile.

Revision ID: 0008_add_feature_flags
Revises: 0007_add_pin_columns
"""
from __future__ import annotations

import json
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0008_add_feature_flags"
down_revision = "0007_add_pin_columns"
branch_labels = None
depends_on = None

DEFAULT_FLAGS = json.dumps({"toc": True, "reading_progress": True, "social_sharing": True})


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("site_profile")}
    if "feature_flags" not in cols:
        op.add_column(
            "site_profile",
            sa.Column("feature_flags", sa.JSON(), server_default=DEFAULT_FLAGS, nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("site_profile")}
    if "feature_flags" in cols:
        with op.batch_alter_table("site_profile") as batch_op:
            batch_op.drop_column("feature_flags")
