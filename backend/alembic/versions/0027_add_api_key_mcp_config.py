"""Add per-API-key MCP configuration.

Revision ID: 0027_add_api_key_mcp_config
Revises: 0026_merge_0025_heads
Create Date: 2026-03-28 13:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0027_add_api_key_mcp_config"
down_revision = "0026_merge_0025_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("mcp_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "mcp_config")
