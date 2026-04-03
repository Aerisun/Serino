"""Add enabled flag to API keys.

Revision ID: 0035_add_api_key_enabled_flag
Revises: 0034_merge_0033_heads
Create Date: 2026-03-29 20:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0035_add_api_key_enabled_flag"
down_revision: Union[str, None] = "0034_merge_0033_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    api_key_columns = {column["name"] for column in inspector.get_columns("api_keys")}

    if "enabled" not in api_key_columns:
        op.add_column(
            "api_keys",
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    api_key_columns = {column["name"] for column in inspector.get_columns("api_keys")}

    if "enabled" in api_key_columns:
        op.drop_column("api_keys", "enabled")
