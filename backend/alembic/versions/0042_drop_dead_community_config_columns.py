"""Drop dead community config columns.

Remove 7 legacy columns that are no longer used: login_mode, draft_enabled,
avatar_presets, guest_avatar_mode, oauth_url, oauth_providers, avatar_strategy.

Revision ID: 0042_drop_dead_community_config_columns
Revises: 0041_add_site_profile_filing_info
Create Date: 2026-04-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0042_drop_dead_community_config_columns"
down_revision = "0041_add_site_profile_filing_info"
branch_labels = None
depends_on = None

DEAD_COLUMNS = [
    "login_mode",
    "draft_enabled",
    "avatar_presets",
    "guest_avatar_mode",
    "oauth_url",
    "oauth_providers",
    "avatar_strategy",
]


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("community_config")}
    with op.batch_alter_table("community_config") as batch_op:
        for col in DEAD_COLUMNS:
            if col in columns:
                batch_op.drop_column(col)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("community_config")}
    with op.batch_alter_table("community_config") as batch_op:
        if "login_mode" not in columns:
            batch_op.add_column(
                sa.Column("login_mode", sa.String(length=40), nullable=False, server_default="disable")
            )
        if "draft_enabled" not in columns:
            batch_op.add_column(sa.Column("draft_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "avatar_presets" not in columns:
            batch_op.add_column(sa.Column("avatar_presets", sa.JSON(), nullable=False, server_default="[]"))
        if "guest_avatar_mode" not in columns:
            batch_op.add_column(
                sa.Column("guest_avatar_mode", sa.String(length=40), nullable=False, server_default="preset")
            )
        if "oauth_url" not in columns:
            batch_op.add_column(sa.Column("oauth_url", sa.String(length=500), nullable=True))
        if "oauth_providers" not in columns:
            batch_op.add_column(sa.Column("oauth_providers", sa.JSON(), nullable=False, server_default="[]"))
        if "avatar_strategy" not in columns:
            batch_op.add_column(
                sa.Column("avatar_strategy", sa.String(length=80), nullable=False, server_default="identicon")
            )
