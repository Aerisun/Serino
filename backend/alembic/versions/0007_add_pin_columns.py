"""Add pin columns to content tables.

Revision ID: 0007_add_pin_columns
Revises: 0006_add_community_config_comment_settings
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0007_add_pin_columns"
down_revision = "0006_add_community_config_comment_settings"
branch_labels = None
depends_on = None

_TABLES = ["posts", "diary_entries", "thoughts", "excerpts"]


def _column_names(inspector: sa.engine.reflection.Inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for table in _TABLES:
        cols = _column_names(inspector, table)
        if "is_pinned" not in cols:
            op.add_column(table, sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("0"), nullable=False))
        if "pin_order" not in cols:
            op.add_column(table, sa.Column("pin_order", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for table in _TABLES:
        cols = _column_names(inspector, table)
        if "pin_order" in cols:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("pin_order")
        if "is_pinned" in cols:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("is_pinned")
