"""Add backup bootstrap claims.

Revision ID: 0009_backup_bootstrap_claims
Revises: 0008_visit_record_order_index
Create Date: 2026-07-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0009_backup_bootstrap_claims"
down_revision = "0008_visit_record_order_index"
branch_labels = None
depends_on = None

TABLE = "backup_bootstrap_claims"
INDEXES = {
    "ix_backup_bootstrap_claims_token_hash": ["token_hash"],
    "ix_backup_bootstrap_claims_status_expires": ["status", "expires_at"],
    "ix_backup_bootstrap_claims_actor_target": [
        "created_by_admin_id",
        "remote_host",
        "remote_port",
        "remote_username",
        "remote_path",
        "status",
    ],
}


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes() -> set[str]:
    if TABLE not in _table_names():
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade() -> None:
    if TABLE not in _table_names():
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("created_by_admin_id", sa.String(length=36), nullable=True),
            sa.Column("site_slug", sa.String(length=120), nullable=False),
            sa.Column("credential_ref", sa.String(length=255), nullable=False),
            sa.Column("remote_host", sa.String(length=255), nullable=False),
            sa.Column("remote_port", sa.Integer(), nullable=False),
            sa.Column("remote_username", sa.String(length=255), nullable=False),
            sa.Column("remote_path", sa.String(length=500), nullable=False),
            sa.Column("public_key_pem", sa.Text(), nullable=False),
            sa.Column("public_key_fingerprint", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    existing = _indexes()
    for name, columns in INDEXES.items():
        if name not in existing:
            op.create_index(name, TABLE, columns, unique=(name == "ix_backup_bootstrap_claims_token_hash"))


def downgrade() -> None:
    if TABLE not in _table_names():
        return
    existing = _indexes()
    for name in reversed(tuple(INDEXES)):
        if name in existing:
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
