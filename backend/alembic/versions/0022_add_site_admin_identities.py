"""add site admin identities

Revision ID: 0022_add_site_admin_identities
Revises: 0021_add_site_auth_config
Create Date: 2026-03-26 21:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_add_site_admin_identities"
down_revision = "0021_add_site_auth_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_auth_config", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "admin_email_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_table(
        "site_admin_identities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_user_id", sa.String(length=36), nullable=False),
        sa.Column("admin_user_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("provider_display_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_user_id"], ["site_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "identifier", name="uq_site_admin_identity_provider_identifier"),
    )


def downgrade() -> None:
    op.drop_table("site_admin_identities")
    with op.batch_alter_table("site_auth_config", schema=None) as batch_op:
        batch_op.drop_column("admin_email_enabled")
