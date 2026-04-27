"""Add configurable comment image upload rate limit.

Revision ID: 0003_comment_image_rate_limit
Revises: 0002_public_title_identity
Create Date: 2026-04-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003_comment_image_rate_limit"
down_revision = "0002_public_title_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("community_config")}
    if "comment_image_rate_limit_count" not in existing_columns:
        op.add_column(
            "community_config",
            sa.Column(
                "comment_image_rate_limit_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("18"),
            ),
        )
    if "comment_image_rate_limit_window_minutes" not in existing_columns:
        op.add_column(
            "community_config",
            sa.Column(
                "comment_image_rate_limit_window_minutes",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("30"),
            ),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("community_config")}
    if "comment_image_rate_limit_window_minutes" in existing_columns:
        op.drop_column("community_config", "comment_image_rate_limit_window_minutes")
    if "comment_image_rate_limit_count" in existing_columns:
        op.drop_column("community_config", "comment_image_rate_limit_count")
