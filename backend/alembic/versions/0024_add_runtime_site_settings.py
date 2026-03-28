"""add runtime site settings

Revision ID: 0024_add_runtime_site_settings
Revises: 0023_add_site_icon_url
Create Date: 2026-03-27 23:20:00.000000
"""

from __future__ import annotations

import json
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0024_add_runtime_site_settings"
down_revision = "0023_add_site_icon_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_site_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("public_site_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("production_cors_origins", sa.JSON(), nullable=False),
        sa.Column("seo_default_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("seo_default_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("rss_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("rss_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("robots_indexing_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sitemap_static_pages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    connection = op.get_bind()
    profile = connection.execute(
        sa.text("SELECT title, meta_description FROM site_profile ORDER BY created_at ASC LIMIT 1")
    ).fetchone()

    title = str(profile[0] or "") if profile is not None else ""
    description = str(profile[1] or "") if profile is not None else ""

    connection.execute(
        sa.text(
            """
            INSERT INTO runtime_site_settings (
                id,
                public_site_url,
                production_cors_origins,
                seo_default_title,
                seo_default_description,
                rss_title,
                rss_description,
                robots_indexing_enabled,
                sitemap_static_pages,
                created_at,
                updated_at
            ) VALUES (
                :id,
                '',
                :production_cors_origins,
                :seo_default_title,
                :seo_default_description,
                :rss_title,
                :rss_description,
                1,
                :sitemap_static_pages,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "id": str(uuid4()),
            "production_cors_origins": json.dumps([]),
            "seo_default_title": title,
            "seo_default_description": description,
            "rss_title": title,
            "rss_description": description,
            "sitemap_static_pages": json.dumps(
                [
                    {"path": "/", "changefreq": "daily", "priority": "1.0"},
                    {"path": "/posts", "changefreq": "daily", "priority": "0.9"},
                    {"path": "/diary", "changefreq": "daily", "priority": "0.8"},
                    {"path": "/thoughts", "changefreq": "weekly", "priority": "0.7"},
                    {"path": "/excerpts", "changefreq": "weekly", "priority": "0.7"},
                    {"path": "/friends", "changefreq": "weekly", "priority": "0.6"},
                    {"path": "/guestbook", "changefreq": "weekly", "priority": "0.5"},
                    {"path": "/resume", "changefreq": "monthly", "priority": "0.6"},
                    {"path": "/calendar", "changefreq": "daily", "priority": "0.5"},
                ]
            ),
        },
    )


def downgrade() -> None:
    op.drop_table("runtime_site_settings")
