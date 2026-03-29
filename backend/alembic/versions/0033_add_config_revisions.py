"""Add config revision history table.

Revision ID: 0033_add_config_revisions
Revises: 0032_add_subscription_initiator_site_user
Create Date: 2026-03-29 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0033_add_config_revisions"
down_revision: Union[str, None] = "0032_add_subscription_initiator_site_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "config_revisions" not in inspector.get_table_names():
        op.create_table(
            "config_revisions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("actor_id", sa.String(length=36), nullable=True),
            sa.Column("resource_key", sa.String(length=120), nullable=False),
            sa.Column("resource_label", sa.String(length=160), nullable=False),
            sa.Column("operation", sa.String(length=40), nullable=False),
            sa.Column("resource_version", sa.String(length=40), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("changed_fields", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("before_snapshot", sa.JSON(), nullable=True),
            sa.Column("after_snapshot", sa.JSON(), nullable=True),
            sa.Column("before_preview", sa.JSON(), nullable=True),
            sa.Column("after_preview", sa.JSON(), nullable=True),
            sa.Column("sensitive_fields", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("restored_from_revision_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_config_revisions_resource_key_created_at",
            "config_revisions",
            ["resource_key", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_config_revisions_actor_id_created_at",
            "config_revisions",
            ["actor_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_config_revisions_restored_from_revision_id",
            "config_revisions",
            ["restored_from_revision_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "config_revisions" in inspector.get_table_names():
        op.drop_index("ix_config_revisions_restored_from_revision_id", table_name="config_revisions")
        op.drop_index("ix_config_revisions_actor_id_created_at", table_name="config_revisions")
        op.drop_index("ix_config_revisions_resource_key_created_at", table_name="config_revisions")
        op.drop_table("config_revisions")
