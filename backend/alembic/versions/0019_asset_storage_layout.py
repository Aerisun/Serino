"""Anchor stable asset storage layout migration and add resource filters.

Revision ID: 0019_asset_storage_layout
Revises: 0018_post_access_requests
Create Date: 2026-08-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0019_asset_storage_layout"
down_revision = "0018_post_access_requests"
branch_labels = None
depends_on = None


def _asset_indexes() -> set[str]:
    inspector = inspect(op.get_bind())
    if "assets" not in inspector.get_table_names():
        return set()
    return {str(index["name"]) for index in inspector.get_indexes("assets")}


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "asset_local_delete_queue_items" not in inspector.get_table_names():
        op.create_table(
            "asset_local_delete_queue_items",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("storage_path", sa.String(length=500), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("retry_count", sa.Integer(), nullable=False),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    existing = _asset_indexes()
    if "ix_assets_scope_category_created_at" not in existing:
        op.create_index(
            "ix_assets_scope_category_created_at",
            "assets",
            ["scope", "category", "created_at"],
        )
    if "ix_assets_remote_object_key" not in existing:
        op.create_index("ix_assets_remote_object_key", "assets", ["remote_object_key"])


def downgrade() -> None:
    existing = _asset_indexes()
    if "ix_assets_remote_object_key" in existing:
        op.drop_index("ix_assets_remote_object_key", table_name="assets")
    if "ix_assets_scope_category_created_at" in existing:
        op.drop_index("ix_assets_scope_category_created_at", table_name="assets")
    inspector = inspect(op.get_bind())
    if "asset_local_delete_queue_items" in inspector.get_table_names():
        op.drop_table("asset_local_delete_queue_items")
