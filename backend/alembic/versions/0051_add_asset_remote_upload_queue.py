"""Add remote upload queue for OSS backfill sync.

Revision ID: 0051_add_asset_remote_upload_queue
Revises: 0050_merge_object_storage_and_site_auth_heads
Create Date: 2026-04-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0051_add_asset_remote_upload_queue"
down_revision = "0050_merge_object_storage_and_site_auth_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "asset_remote_upload_queue_items" not in inspector.get_table_names():
        op.create_table(
            "asset_remote_upload_queue_items",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("asset_id", sa.String(length=36), nullable=False),
            sa.Column("object_key", sa.String(length=500), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "asset_remote_upload_queue_items" in inspector.get_table_names():
        op.drop_table("asset_remote_upload_queue_items")
