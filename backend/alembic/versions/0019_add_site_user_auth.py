"""add site user auth

Revision ID: 0019_add_site_user_auth
Revises: 0018_add_asset_scope
Create Date: 2026-03-26 12:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_add_site_user_auth"
down_revision = "0018_add_asset_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=False),
        sa.Column("primary_auth_provider", sa.String(length=40), nullable=False, server_default="email"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "site_user_oauth_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=255), nullable=True),
        sa.Column("provider_display_name", sa.String(length=120), nullable=True),
        sa.Column("provider_avatar_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_user_id"], ["site_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_site_user_oauth_provider_subject"),
    )
    op.create_table(
        "site_user_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_user_id", sa.String(length=36), nullable=False),
        sa.Column("session_token", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_user_id"], ["site_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token"),
    )
    op.execute("UPDATE community_config SET login_mode = 'force', anonymous_enabled = 0")


def downgrade() -> None:
    op.drop_table("site_user_sessions")
    op.drop_table("site_user_oauth_accounts")
    op.drop_table("site_users")
