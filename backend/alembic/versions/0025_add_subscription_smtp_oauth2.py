"""add subscription smtp oauth2 fields

Revision ID: 0025_add_subscription_smtp_oauth2
Revises: 0024_add_content_subscriptions
Create Date: 2026-03-28 00:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_add_subscription_smtp_oauth2"
down_revision = "0024_add_content_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_subscription_config") as batch_op:
        batch_op.add_column(sa.Column("smtp_auth_mode", sa.String(length=32), nullable=False, server_default="password"))
        batch_op.add_column(sa.Column("smtp_oauth_tenant", sa.String(length=120), nullable=False, server_default="common"))
        batch_op.add_column(sa.Column("smtp_oauth_client_id", sa.String(length=255), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("smtp_oauth_client_secret", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("smtp_oauth_refresh_token", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("content_subscription_config") as batch_op:
        batch_op.drop_column("smtp_oauth_refresh_token")
        batch_op.drop_column("smtp_oauth_client_secret")
        batch_op.drop_column("smtp_oauth_client_id")
        batch_op.drop_column("smtp_oauth_tenant")
        batch_op.drop_column("smtp_auth_mode")
