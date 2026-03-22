"""Add nav_items table and content metadata columns."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004_add_nav_and_content_metadata"
down_revision = "0003_add_site_hero_video_url"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.InspectionAttr, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("nav_items"):
        op.create_table(
            "nav_items",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("site_profile_id", sa.String(length=36), sa.ForeignKey("site_profile.id", ondelete="CASCADE"), nullable=False),
            sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("nav_items.id", ondelete="CASCADE"), nullable=True),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("href", sa.String(length=500), nullable=True),
            sa.Column("icon_key", sa.String(length=80), nullable=True),
            sa.Column("page_key", sa.String(length=80), nullable=True),
            sa.Column("trigger", sa.String(length=40), nullable=False, server_default="none"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    posts_columns = _column_names(inspector, "posts")
    with op.batch_alter_table("posts") as batch_op:
        if "category" not in posts_columns:
            batch_op.add_column(sa.Column("category", sa.String(length=80), nullable=True))
        if "view_count" not in posts_columns:
            batch_op.add_column(sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))

    diary_columns = _column_names(inspector, "diary_entries")
    with op.batch_alter_table("diary_entries") as batch_op:
        if "mood" not in diary_columns:
            batch_op.add_column(sa.Column("mood", sa.String(length=40), nullable=True))
        if "weather" not in diary_columns:
            batch_op.add_column(sa.Column("weather", sa.String(length=40), nullable=True))
        if "poem" not in diary_columns:
            batch_op.add_column(sa.Column("poem", sa.Text(), nullable=True))
        if "view_count" not in diary_columns:
            batch_op.add_column(sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))

    thoughts_columns = _column_names(inspector, "thoughts")
    with op.batch_alter_table("thoughts") as batch_op:
        if "mood" not in thoughts_columns:
            batch_op.add_column(sa.Column("mood", sa.String(length=40), nullable=True))
        if "view_count" not in thoughts_columns:
            batch_op.add_column(sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))

    excerpts_columns = _column_names(inspector, "excerpts")
    with op.batch_alter_table("excerpts") as batch_op:
        if "author_name" not in excerpts_columns:
            batch_op.add_column(sa.Column("author_name", sa.String(length=160), nullable=True))
        if "source" not in excerpts_columns:
            batch_op.add_column(sa.Column("source", sa.String(length=300), nullable=True))
        if "view_count" not in excerpts_columns:
            batch_op.add_column(sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    excerpts_columns = _column_names(inspector, "excerpts")
    with op.batch_alter_table("excerpts") as batch_op:
        if "view_count" in excerpts_columns:
            batch_op.drop_column("view_count")
        if "source" in excerpts_columns:
            batch_op.drop_column("source")
        if "author_name" in excerpts_columns:
            batch_op.drop_column("author_name")

    thoughts_columns = _column_names(inspector, "thoughts")
    with op.batch_alter_table("thoughts") as batch_op:
        if "view_count" in thoughts_columns:
            batch_op.drop_column("view_count")
        if "mood" in thoughts_columns:
            batch_op.drop_column("mood")

    diary_columns = _column_names(inspector, "diary_entries")
    with op.batch_alter_table("diary_entries") as batch_op:
        if "view_count" in diary_columns:
            batch_op.drop_column("view_count")
        if "poem" in diary_columns:
            batch_op.drop_column("poem")
        if "weather" in diary_columns:
            batch_op.drop_column("weather")
        if "mood" in diary_columns:
            batch_op.drop_column("mood")

    posts_columns = _column_names(inspector, "posts")
    with op.batch_alter_table("posts") as batch_op:
        if "view_count" in posts_columns:
            batch_op.drop_column("view_count")
        if "category" in posts_columns:
            batch_op.drop_column("category")

    if inspector.has_table("nav_items"):
        op.drop_table("nav_items")
