from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _content_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="public"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    ]


def upgrade() -> None:
    op.create_table(
        "site_profile",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=160), nullable=False),
        sa.Column("footer_text", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "social_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_profile_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("href", sa.String(length=500), nullable=False),
        sa.Column("icon_key", sa.String(length=80), nullable=False),
        sa.Column("placement", sa.String(length=40), nullable=False, server_default="hero"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["site_profile_id"], ["site_profile.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "poems",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_profile_id", sa.String(length=36), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["site_profile_id"], ["site_profile.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "page_copy",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("page_key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("search_placeholder", sa.String(length=200), nullable=True),
        sa.Column("empty_message", sa.Text(), nullable=True),
        sa.Column("max_width", sa.String(length=40), nullable=True),
        sa.Column("page_size", sa.Integer(), nullable=True),
        sa.Column("download_label", sa.String(length=80), nullable=True),
        sa.Column("extras", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_key"),
    )

    op.create_table(
        "page_display_options",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("page_key", sa.String(length=80), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("settings", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_key"),
    )

    op.create_table(
        "community_config",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False, server_default="waline"),
        sa.Column("server_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("surfaces", sa.JSON(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("required_meta", sa.JSON(), nullable=False),
        sa.Column("emoji_presets", sa.JSON(), nullable=False),
        sa.Column("enable_enjoy_search", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("image_uploader", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("login_mode", sa.String(length=40), nullable=False, server_default="disable"),
        sa.Column("oauth_url", sa.String(length=500), nullable=True),
        sa.Column("avatar_strategy", sa.String(length=80), nullable=False, server_default="identicon"),
        sa.Column("migration_state", sa.String(length=40), nullable=False, server_default="not_started"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "resume_basics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("subtitle", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("download_label", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "resume_skills",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resume_basics_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["resume_basics_id"], ["resume_basics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "resume_experiences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resume_basics_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("company", sa.String(length=160), nullable=False),
        sa.Column("period", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["resume_basics_id"], ["resume_basics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("posts", *_content_columns())
    op.create_table("diary_entries", *_content_columns())
    op.create_table("thoughts", *_content_columns())
    op.create_table("excerpts", *_content_columns())

    op.create_table(
        "guestbook_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("content_slug", sa.String(length=160), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("author_name", sa.String(length=120), nullable=False),
        sa.Column("author_email", sa.String(length=320), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("content_slug", sa.String(length=160), nullable=False),
        sa.Column("reaction_type", sa.String(length=80), nullable=False),
        sa.Column("client_token", sa.String(length=160), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "friends",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "friend_feed_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("friend_id", sa.String(length=36), nullable=False),
        sa.Column("feed_url", sa.String(length=500), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["friend_id"], ["friends.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "friend_feed_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["source_id"], ["friend_feed_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=128), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("admin_user_id", sa.String(length=36), nullable=False),
        sa.Column("session_token", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key_name", sa.String(length=160), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("hashed_secret", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_prefix"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=80), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "moderation_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "backup_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("db_path", sa.String(length=500), nullable=False),
        sa.Column("replica_url", sa.String(length=500), nullable=True),
        sa.Column("backup_path", sa.String(length=500), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "restore_points",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("db_path", sa.String(length=500), nullable=False),
        sa.Column("point_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_table("restore_points")
    op.drop_table("backup_snapshots")
    op.drop_table("moderation_records")
    op.drop_table("audit_logs")
    op.drop_table("api_keys")
    op.drop_table("admin_sessions")
    op.drop_table("admin_users")
    op.drop_table("assets")
    op.drop_table("friend_feed_items")
    op.drop_table("friend_feed_sources")
    op.drop_table("friends")
    op.drop_table("reactions")
    op.drop_table("comments")
    op.drop_table("guestbook_entries")
    op.drop_table("excerpts")
    op.drop_table("thoughts")
    op.drop_table("diary_entries")
    op.drop_table("posts")
    op.drop_table("resume_experiences")
    op.drop_table("resume_skills")
    op.drop_table("resume_basics")
    op.drop_table("community_config")
    op.drop_table("page_display_options")
    op.drop_table("page_copy")
    op.drop_table("poems")
    op.drop_table("social_links")
    op.drop_table("site_profile")
