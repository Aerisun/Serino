"""Add per-post access requests.

Revision ID: 0018_post_access_requests
Revises: 0017_post_requires_approval
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0018_post_access_requests"
down_revision = "0017_post_requires_approval"
branch_labels = None
depends_on = None

TABLE = "post_access_requests"
INDEXES = {
    "ix_post_access_requests_post_id": ["post_id"],
    "ix_post_access_requests_site_user_id": ["site_user_id"],
    "ix_post_access_requests_status": ["status"],
    "ix_post_access_requests_post_user_created_id": ["post_id", "site_user_id", "created_at", "id"],
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
            sa.Column("post_id", sa.String(length=36), nullable=False),
            sa.Column("site_user_id", sa.String(length=36), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_by_admin_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["site_user_id"], ["site_users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewed_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    existing = _indexes()
    for name, columns in INDEXES.items():
        if name not in existing:
            op.create_index(name, TABLE, columns)


def downgrade() -> None:
    if TABLE not in _table_names():
        return
    existing = _indexes()
    for name in reversed(tuple(INDEXES)):
        if name in existing:
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
