"""Merge automation and subscription migration heads.

Revision ID: 0026_merge_0025_heads
Revises: 0025_add_automation_tables, 0025_add_subscription_smtp_oauth2
Create Date: 2026-03-28 11:00:00.000000
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0026_merge_0025_heads"
down_revision = ("0025_add_automation_tables", "0025_add_subscription_smtp_oauth2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
