"""Drop legacy backup snapshot tables.

Revision ID: 0038_drop_legacy_backup_snapshot_tables
Revises: 0037_add_workflow_pack_runtime_tables
Create Date: 2026-04-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0038_drop_legacy_backup_snapshot_tables"
down_revision = "0037_add_workflow_pack_runtime_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "restore_points" in tables:
        op.drop_table("restore_points")
    if "backup_snapshots" in tables:
        op.drop_table("backup_snapshots")


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "backup_snapshots" not in tables:
        op.create_table(
            "backup_snapshots",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("snapshot_type", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("db_path", sa.String(length=500), nullable=False),
            sa.Column("replica_url", sa.String(length=500)),
            sa.Column("backup_path", sa.String(length=500)),
            sa.Column("checksum", sa.String(length=128)),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "restore_points" not in tables:
        op.create_table(
            "restore_points",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("snapshot_id", sa.String(length=36)),
            sa.Column("db_path", sa.String(length=500), nullable=False),
            sa.Column("point_in_time", sa.DateTime(timezone=True)),
            sa.Column("notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
