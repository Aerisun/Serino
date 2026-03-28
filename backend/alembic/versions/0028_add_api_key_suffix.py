"""Add API key suffix hint column.

Revision ID: 0028_add_api_key_suffix
Revises: 0027_add_api_key_mcp_config
Create Date: 2026-03-28 16:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0028_add_api_key_suffix"
down_revision = "0027_add_api_key_mcp_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("key_suffix", sa.String(length=16), nullable=True))

    # Hard cutover: invalidate all pre-existing API keys.
    op.execute(sa.text("DELETE FROM api_keys"))

    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.alter_column("key_suffix", existing_type=sa.String(length=16), nullable=False)


def downgrade() -> None:
    op.drop_column("api_keys", "key_suffix")
