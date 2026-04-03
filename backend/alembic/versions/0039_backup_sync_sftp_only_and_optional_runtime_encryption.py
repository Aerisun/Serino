"""Make backup sync SFTP-only and add optional runtime encryption.

Revision ID: 0039_backup_sync_sftp_only_and_optional_runtime_encryption
Revises: 0038_drop_legacy_backup_snapshot_tables
Create Date: 2026-04-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0039_backup_sync_sftp_only_and_optional_runtime_encryption"
down_revision = "0038_drop_legacy_backup_snapshot_tables"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {str(row["name"]) for row in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "backup_target_configs" in tables:
        columns = _column_names(inspector, "backup_target_configs")
        with op.batch_alter_table("backup_target_configs") as batch_op:
            if "encrypt_runtime_data" not in columns:
                batch_op.add_column(
                    sa.Column("encrypt_runtime_data", sa.Boolean(), nullable=False, server_default=sa.text("0"))
                )
            if "receiver_base_url" in columns:
                batch_op.drop_column("receiver_base_url")
            if "age_public_key_fingerprint" in columns:
                batch_op.drop_column("age_public_key_fingerprint")
        bind.execute(sa.text("UPDATE backup_target_configs SET transport_mode = 'sftp'"))

    if "backup_queue_items" in tables:
        bind.execute(sa.text("UPDATE backup_queue_items SET transport = 'sftp' WHERE transport != 'sftp'"))
    if "backup_commits" in tables:
        bind.execute(sa.text("UPDATE backup_commits SET transport = 'sftp' WHERE transport != 'sftp'"))
    if "sync_runs" in tables:
        bind.execute(sa.text("UPDATE sync_runs SET transport = 'sftp' WHERE transport != 'sftp'"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "backup_target_configs" not in tables:
        return

    columns = _column_names(inspector, "backup_target_configs")
    with op.batch_alter_table("backup_target_configs") as batch_op:
        if "receiver_base_url" not in columns:
            batch_op.add_column(sa.Column("receiver_base_url", sa.String(length=500), nullable=True))
        if "age_public_key_fingerprint" not in columns:
            batch_op.add_column(sa.Column("age_public_key_fingerprint", sa.String(length=255), nullable=True))
        if "encrypt_runtime_data" in columns:
            batch_op.drop_column("encrypt_runtime_data")
