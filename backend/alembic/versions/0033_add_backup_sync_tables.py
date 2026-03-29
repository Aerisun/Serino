"""add backup sync tables

Revision ID: 0033_add_backup_sync_tables
Revises: 0032_add_subscription_initiator_site_user
Create Date: 2026-03-29 02:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0033_add_backup_sync_tables"
down_revision = "0032_add_subscription_initiator_site_user"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())

    sync_run_columns = _column_names(inspector, "sync_runs")
    if "sync_runs" in tables:
        with op.batch_alter_table("sync_runs") as batch_op:
            if "transport" not in sync_run_columns:
                batch_op.add_column(sa.Column("transport", sa.String(length=32), nullable=True))
            if "trigger_kind" not in sync_run_columns:
                batch_op.add_column(sa.Column("trigger_kind", sa.String(length=32), nullable=True))
            if "queue_item_id" not in sync_run_columns:
                batch_op.add_column(sa.Column("queue_item_id", sa.String(length=36), nullable=True))
            if "commit_id" not in sync_run_columns:
                batch_op.add_column(sa.Column("commit_id", sa.String(length=36), nullable=True))
            if "stats_json" not in sync_run_columns:
                batch_op.add_column(sa.Column("stats_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
            if "retry_count" not in sync_run_columns:
                batch_op.add_column(sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
            if "next_retry_at" not in sync_run_columns:
                batch_op.add_column(sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
            if "last_error" not in sync_run_columns:
                batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))
    else:
        op.create_table(
            "sync_runs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("job_name", sa.String(length=160), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("transport", sa.String(length=32), nullable=True),
            sa.Column("trigger_kind", sa.String(length=32), nullable=True),
            sa.Column("queue_item_id", sa.String(length=36), nullable=True),
            sa.Column("commit_id", sa.String(length=36), nullable=True),
            sa.Column("stats_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "backup_target_configs" not in tables:
        op.create_table(
            "backup_target_configs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("transport_mode", sa.String(length=32), nullable=False, server_default="receiver"),
            sa.Column("site_slug", sa.String(length=120), nullable=False, server_default="aerisun"),
            sa.Column("receiver_base_url", sa.String(length=500), nullable=True),
            sa.Column("remote_host", sa.String(length=255), nullable=True),
            sa.Column("remote_port", sa.Integer(), nullable=True),
            sa.Column("remote_path", sa.String(length=500), nullable=True),
            sa.Column("remote_username", sa.String(length=255), nullable=True),
            sa.Column("credential_ref", sa.String(length=255), nullable=True),
            sa.Column("age_public_key_fingerprint", sa.String(length=255), nullable=True),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("retry_backoff_seconds", sa.Integer(), nullable=False, server_default="300"),
            sa.Column("last_scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "backup_queue_items" not in tables:
        op.create_table(
            "backup_queue_items",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("transport", sa.String(length=32), nullable=False),
            sa.Column("trigger_kind", sa.String(length=32), nullable=False, server_default="scheduled"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("dataset_versions", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("verified_chunks", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "backup_commits" not in tables:
        op.create_table(
            "backup_commits",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("transport", sa.String(length=32), nullable=False),
            sa.Column("trigger_kind", sa.String(length=32), nullable=False, server_default="scheduled"),
            sa.Column("site_slug", sa.String(length=120), nullable=False),
            sa.Column("remote_commit_id", sa.String(length=255), nullable=False),
            sa.Column("manifest_digest", sa.String(length=128), nullable=False),
            sa.Column("backup_path", sa.String(length=500), nullable=True),
            sa.Column("datasets", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("stats_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("snapshot_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("snapshot_finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("backup_commits")
    op.drop_table("backup_queue_items")
    op.drop_table("backup_target_configs")
    with op.batch_alter_table("sync_runs") as batch_op:
        batch_op.drop_column("last_error")
        batch_op.drop_column("next_retry_at")
        batch_op.drop_column("retry_count")
        batch_op.drop_column("stats_json")
        batch_op.drop_column("commit_id")
        batch_op.drop_column("queue_item_id")
        batch_op.drop_column("trigger_kind")
        batch_op.drop_column("transport")
