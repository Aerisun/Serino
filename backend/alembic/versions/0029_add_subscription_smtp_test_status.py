"""add subscription smtp test status fields

Revision ID: 0029_add_subscription_smtp_test_status
Revises: 0028_add_api_key_suffix
Create Date: 2026-03-28 20:50:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_add_subscription_smtp_test_status"
down_revision = "0028_add_api_key_suffix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_subscription_config") as batch_op:
        batch_op.add_column(
            sa.Column("smtp_test_passed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("smtp_tested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content_subscription_config") as batch_op:
        batch_op.drop_column("smtp_tested_at")
        batch_op.drop_column("smtp_test_passed")
