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
from sqlalchemy import inspect

revision = "0021_add_site_auth_config"
down_revision = "0020_merge_0019_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "site_auth_config" not in existing_tables:
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
        existing_tables.add("site_auth_config")

    connection = op.get_bind()
    config_columns = {column["name"] for column in inspector.get_columns("site_auth_config")}
    visitor_oauth_providers = ["github", "google"]
    if "community_config" in existing_tables:
        community_columns = {column["name"] for column in inspector.get_columns("community_config")}
        if "oauth_providers" in community_columns:
            community = connection.execute(sa.text("SELECT oauth_providers FROM community_config LIMIT 1")).fetchone()
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

    existing_row = connection.execute(sa.text("SELECT id FROM site_auth_config LIMIT 1")).fetchone()
    if existing_row is None:
        insert_columns = [
            "id",
            "email_login_enabled",
            "visitor_oauth_providers",
            "admin_auth_methods",
        ]
        insert_values = [
            ":id",
            ":email_login_enabled",
            ":visitor_oauth_providers",
            ":admin_auth_methods",
        ]
        insert_params: dict[str, object] = {
            "id": str(uuid4()),
            "email_login_enabled": True,
            "visitor_oauth_providers": json.dumps(visitor_oauth_providers),
            "admin_auth_methods": json.dumps(["email"]),
        }

        if "admin_email_enabled" in config_columns:
            insert_columns.append("admin_email_enabled")
            insert_values.append(":admin_email_enabled")
            insert_params["admin_email_enabled"] = False

        insert_columns.extend(
            [
                "google_client_id",
                "google_client_secret",
                "github_client_id",
                "github_client_secret",
                "created_at",
                "updated_at",
            ]
        )
        insert_values.extend(
            [
                "''",
                "''",
                "''",
                "''",
                "CURRENT_TIMESTAMP",
                "CURRENT_TIMESTAMP",
            ]
        )

        connection.execute(
            sa.text(
                f"""
                INSERT INTO site_auth_config (
                    {", ".join(insert_columns)}
                ) VALUES (
                    {", ".join(insert_values)}
                )
                """
            ),
            insert_params,
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "site_auth_config" in inspector.get_table_names():
        op.drop_table("site_auth_config")
