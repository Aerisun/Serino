"""Add backup recovery key escrow table.

Revision ID: 0040_add_backup_recovery_keys
Revises: 0039_backup_sync_sftp_only_and_optional_runtime_encryption
Create Date: 2026-04-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0040_add_backup_recovery_keys"
down_revision = "0039_backup_sync_sftp_only_and_optional_runtime_encryption"
branch_labels = None
depends_on = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "backup_recovery_keys" not in tables:
        op.create_table(
            "backup_recovery_keys",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("credential_ref", sa.String(length=255), nullable=False),
            sa.Column("site_slug", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("secrets_fingerprint", sa.String(length=255), nullable=False),
            sa.Column("secrets_public_pem", sa.Text(), nullable=False),
            sa.Column("encrypted_private_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("archived_at", sa.DateTime(timezone=True)),
            sa.Column("last_exported_at", sa.DateTime(timezone=True)),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        tables.add("backup_recovery_keys")

    if not _has_index(inspector, "backup_recovery_keys", "ix_backup_recovery_keys_credential_status"):
        op.create_index(
            "ix_backup_recovery_keys_credential_status",
            "backup_recovery_keys",
            ["credential_ref", "status", "created_at"],
        )
    if not _has_index(inspector, "backup_recovery_keys", "ix_backup_recovery_keys_fingerprint"):
        op.create_index(
            "ix_backup_recovery_keys_fingerprint",
            "backup_recovery_keys",
            ["secrets_fingerprint"],
        )


def downgrade() -> None:
    op.drop_index("ix_backup_recovery_keys_fingerprint", table_name="backup_recovery_keys")
    op.drop_index("ix_backup_recovery_keys_credential_status", table_name="backup_recovery_keys")
    op.drop_table("backup_recovery_keys")
