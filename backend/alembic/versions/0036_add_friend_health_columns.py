"""Add friend website health tracking columns.

Revision ID: 0036_add_friend_health_columns
Revises: 0035_add_api_key_enabled_flag
Create Date: 2026-03-29 20:55:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0036_add_friend_health_columns"
down_revision: Union[str, None] = "0035_add_api_key_enabled_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("friends"):
        return
    friend_columns = {column["name"] for column in inspector.get_columns("friends")}

    if "last_checked_at" not in friend_columns:
        op.add_column("friends", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    if "last_error" not in friend_columns:
        op.add_column("friends", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("friends"):
        return
    friend_columns = {column["name"] for column in inspector.get_columns("friends")}

    if "last_error" in friend_columns:
        op.drop_column("friends", "last_error")
    if "last_checked_at" in friend_columns:
        op.drop_column("friends", "last_checked_at")
