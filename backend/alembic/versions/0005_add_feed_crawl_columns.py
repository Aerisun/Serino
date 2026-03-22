"""Add etag and last_error columns to friend_feed_sources."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0005_add_feed_crawl_columns"
down_revision = "0004_add_nav_and_content_metadata"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.engine.reflection.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("friend_feed_sources"):
        return

    existing = _column_names(inspector, "friend_feed_sources")
    with op.batch_alter_table("friend_feed_sources") as batch_op:
        if "etag" not in existing:
            batch_op.add_column(sa.Column("etag", sa.String(500), nullable=True))
        if "last_error" not in existing:
            batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    existing = _column_names(inspector, "friend_feed_sources")
    with op.batch_alter_table("friend_feed_sources") as batch_op:
        if "last_error" in existing:
            batch_op.drop_column("last_error")
        if "etag" in existing:
            batch_op.drop_column("etag")
