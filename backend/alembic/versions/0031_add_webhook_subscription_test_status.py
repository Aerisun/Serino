"""add webhook subscription test status fields

Revision ID: 0031_add_webhook_subscription_test_status
Revises: 0030_add_subscription_delivery_and_templates
Create Date: 2026-03-28 23:55:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_add_webhook_subscription_test_status"
down_revision = "0030_add_subscription_delivery_and_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.add_column(sa.Column("last_test_status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("last_test_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.drop_column("last_tested_at")
        batch_op.drop_column("last_test_error")
        batch_op.drop_column("last_test_status")
