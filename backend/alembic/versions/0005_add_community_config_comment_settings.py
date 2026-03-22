"""Add comment system settings to community_config."""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0005_add_community_config_comment_settings"
down_revision = "0004_add_nav_and_content_metadata"
branch_labels = None
depends_on = None


DEFAULT_AVATAR_PRESETS = [
    {
        "key": "shiro",
        "label": "Shiro",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Shiro",
    },
    {
        "key": "glass",
        "label": "Glass",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Glass",
    },
    {
        "key": "aurora",
        "label": "Aurora",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Aurora",
    },
    {
        "key": "paper",
        "label": "Paper",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Paper",
    },
    {
        "key": "dawn",
        "label": "Dawn",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Dawn",
    },
    {
        "key": "pebble",
        "label": "Pebble",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Pebble",
    },
]


def _column_names(inspector: sa.InspectionAttr, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _json_default(value: object) -> sa.TextClause:
    return sa.text(f"'{json.dumps(value, ensure_ascii=False)}'")


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if not inspector.has_table("community_config"):
        return

    community_columns = _column_names(inspector, "community_config")
    with op.batch_alter_table("community_config") as batch_op:
        if "oauth_providers" not in community_columns:
            batch_op.add_column(
                sa.Column(
                    "oauth_providers",
                    sa.JSON(),
                    nullable=False,
                    server_default=_json_default(["github", "google"]),
                )
            )
        if "anonymous_enabled" not in community_columns:
            batch_op.add_column(
                sa.Column("anonymous_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
            )
        if "moderation_mode" not in community_columns:
            batch_op.add_column(
                sa.Column("moderation_mode", sa.String(length=40), nullable=False, server_default="all_pending")
            )
        if "default_sorting" not in community_columns:
            batch_op.add_column(
                sa.Column("default_sorting", sa.String(length=40), nullable=False, server_default="latest")
            )
        if "page_size" not in community_columns:
            batch_op.add_column(sa.Column("page_size", sa.Integer(), nullable=False, server_default="20"))
        if "avatar_presets" not in community_columns:
            batch_op.add_column(
                sa.Column(
                    "avatar_presets",
                    sa.JSON(),
                    nullable=False,
                    server_default=_json_default(DEFAULT_AVATAR_PRESETS),
                )
            )
        if "guest_avatar_mode" not in community_columns:
            batch_op.add_column(
                sa.Column("guest_avatar_mode", sa.String(length=40), nullable=False, server_default="preset")
            )
        if "draft_enabled" not in community_columns:
            batch_op.add_column(
                sa.Column("draft_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
            )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if not inspector.has_table("community_config"):
        return

    community_columns = _column_names(inspector, "community_config")
    with op.batch_alter_table("community_config") as batch_op:
        if "draft_enabled" in community_columns:
            batch_op.drop_column("draft_enabled")
        if "guest_avatar_mode" in community_columns:
            batch_op.drop_column("guest_avatar_mode")
        if "avatar_presets" in community_columns:
            batch_op.drop_column("avatar_presets")
        if "page_size" in community_columns:
            batch_op.drop_column("page_size")
        if "default_sorting" in community_columns:
            batch_op.drop_column("default_sorting")
        if "moderation_mode" in community_columns:
            batch_op.drop_column("moderation_mode")
        if "anonymous_enabled" in community_columns:
            batch_op.drop_column("anonymous_enabled")
        if "oauth_providers" in community_columns:
            batch_op.drop_column("oauth_providers")
