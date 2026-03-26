"""add site auth config

Revision ID: 0021_add_site_auth_config
Revises: 0020_merge_0019_heads
Create Date: 2026-03-26 19:20:00.000000
"""

from __future__ import annotations

import json
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0021_add_site_auth_config"
down_revision = "0020_merge_0019_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_auth_config",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email_login_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("visitor_oauth_providers", sa.JSON(), nullable=False),
        sa.Column("admin_auth_methods", sa.JSON(), nullable=False),
        sa.Column("google_client_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("google_client_secret", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("github_client_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("github_client_secret", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    connection = op.get_bind()
    community = connection.execute(sa.text("SELECT oauth_providers FROM community_config LIMIT 1")).fetchone()
    visitor_oauth_providers = ["github", "google"]
    if community is not None and community[0]:
        try:
            parsed = json.loads(community[0]) if isinstance(community[0], str) else list(community[0])
            normalized: list[str] = []
            for provider in parsed:
                if provider not in {"google", "github"} or provider in normalized:
                    continue
                normalized.append(provider)
            visitor_oauth_providers = normalized or ["github", "google"]
        except Exception:
            visitor_oauth_providers = ["github", "google"]

    connection.execute(
        sa.text(
            """
            INSERT INTO site_auth_config (
                id,
                email_login_enabled,
                visitor_oauth_providers,
                admin_auth_methods,
                google_client_id,
                google_client_secret,
                github_client_id,
                github_client_secret,
                created_at,
                updated_at
            ) VALUES (
                :id,
                :email_login_enabled,
                :visitor_oauth_providers,
                :admin_auth_methods,
                '',
                '',
                '',
                '',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "id": str(uuid4()),
            "email_login_enabled": True,
            "visitor_oauth_providers": json.dumps(visitor_oauth_providers),
            "admin_auth_methods": json.dumps(["email"]),
        },
    )


def downgrade() -> None:
    op.drop_table("site_auth_config")
