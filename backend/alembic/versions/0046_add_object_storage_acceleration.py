"""Add object storage acceleration models and asset state fields.

Revision ID: 0046_add_object_storage_acceleration
Revises: 0045_change_default_poem_source_to_hitokoto
Create Date: 2026-04-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0046_add_object_storage_acceleration"
down_revision = "0045_change_default_poem_source_to_hitokoto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    asset_columns = {column["name"] for column in inspector.get_columns("assets")}
    with op.batch_alter_table("assets") as batch_op:
        if "storage_provider" not in asset_columns:
            batch_op.add_column(sa.Column("storage_provider", sa.String(length=32), nullable=False, server_default="local"))
        if "remote_object_key" not in asset_columns:
            batch_op.add_column(sa.Column("remote_object_key", sa.String(length=500), nullable=True))
        if "remote_status" not in asset_columns:
            batch_op.add_column(sa.Column("remote_status", sa.String(length=32), nullable=False, server_default="none"))
        if "remote_uploaded_at" not in asset_columns:
            batch_op.add_column(sa.Column("remote_uploaded_at", sa.DateTime(timezone=True), nullable=True))
        if "remote_etag" not in asset_columns:
            batch_op.add_column(sa.Column("remote_etag", sa.String(length=255), nullable=True))
        if "mirror_status" not in asset_columns:
            batch_op.add_column(sa.Column("mirror_status", sa.String(length=32), nullable=False, server_default="completed"))
        if "mirror_last_error" not in asset_columns:
            batch_op.add_column(sa.Column("mirror_last_error", sa.Text(), nullable=True))
        if "oss_acceleration_enabled_at_upload" not in asset_columns:
            batch_op.add_column(
                sa.Column(
                    "oss_acceleration_enabled_at_upload",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )

    if "object_storage_configs" not in inspector.get_table_names():
        op.create_table(
            "object_storage_configs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="bitiful"),
            sa.Column("bucket", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("endpoint", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("region", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("public_base_url", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("access_key", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("secret_key", sa.Text(), nullable=False, server_default=""),
            sa.Column("cdn_token_key", sa.Text(), nullable=False, server_default=""),
            sa.Column("health_check_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("upload_expire_seconds", sa.Integer(), nullable=False, server_default="300"),
            sa.Column("public_download_expire_seconds", sa.Integer(), nullable=False, server_default="600"),
            sa.Column("mirror_bandwidth_limit_bps", sa.Integer(), nullable=False, server_default=str(2 * 1024 * 1024)),
            sa.Column("mirror_retry_count", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("last_health_ok", sa.Boolean(), nullable=True),
            sa.Column("last_health_error", sa.Text(), nullable=True),
            sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "asset_mirror_queue_items" not in inspector.get_table_names():
        op.create_table(
            "asset_mirror_queue_items",
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

    if "asset_remote_delete_queue_items" not in inspector.get_table_names():
        op.create_table(
            "asset_remote_delete_queue_items",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
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

    if "asset_mirror_queue_items" in inspector.get_table_names():
        op.drop_table("asset_mirror_queue_items")

    if "asset_remote_delete_queue_items" in inspector.get_table_names():
        op.drop_table("asset_remote_delete_queue_items")

    if "object_storage_configs" in inspector.get_table_names():
        op.drop_table("object_storage_configs")

    asset_columns = {column["name"] for column in inspector.get_columns("assets")}
    with op.batch_alter_table("assets") as batch_op:
        if "oss_acceleration_enabled_at_upload" in asset_columns:
            batch_op.drop_column("oss_acceleration_enabled_at_upload")
        if "mirror_last_error" in asset_columns:
            batch_op.drop_column("mirror_last_error")
        if "mirror_status" in asset_columns:
            batch_op.drop_column("mirror_status")
        if "remote_etag" in asset_columns:
            batch_op.drop_column("remote_etag")
        if "remote_uploaded_at" in asset_columns:
            batch_op.drop_column("remote_uploaded_at")
        if "remote_status" in asset_columns:
            batch_op.drop_column("remote_status")
        if "remote_object_key" in asset_columns:
            batch_op.drop_column("remote_object_key")
        if "storage_provider" in asset_columns:
            batch_op.drop_column("storage_provider")
