"""add content subscriptions

Revision ID: 0024_add_content_subscriptions
Revises: 0023_add_site_icon_url
Create Date: 2026-03-27 16:20:00.000000
"""

from __future__ import annotations
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0024_add_content_subscriptions"
down_revision = "0023_add_site_icon_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_subscription_config",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("smtp_host", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_username", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("smtp_password", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("smtp_from_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("smtp_from_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("smtp_reply_to", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("smtp_use_ssl", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "content_subscribers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("content_types", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "content_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content_slug", sa.String(length=160), nullable=False),
        sa.Column("content_title", sa.String(length=240), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("content_url", sa.String(length=500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_type", "content_slug", name="uq_content_notifications_type_slug"),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO content_subscription_config (
                id,
                enabled,
                smtp_host,
                smtp_port,
                smtp_username,
                smtp_password,
                smtp_from_email,
                smtp_from_name,
                smtp_reply_to,
                smtp_use_tls,
                smtp_use_ssl,
                created_at,
                updated_at
            ) VALUES (
                :id,
                :enabled,
                '',
                587,
                '',
                '',
                '',
                '',
                '',
                :smtp_use_tls,
                :smtp_use_ssl,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "id": str(uuid4()),
            "enabled": False,
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )


def downgrade() -> None:
    op.drop_table("content_notifications")
    op.drop_table("content_subscribers")
    op.drop_table("content_subscription_config")
