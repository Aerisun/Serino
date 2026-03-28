"""add hero image and poster urls

Revision ID: 0016_add_hero_image_fields
Revises: 0015_add_asset_note
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0016_add_hero_image_fields"
down_revision = "0015_add_asset_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {column["name"] for column in inspect(op.get_bind()).get_columns("site_profile")}

    if "hero_image_url" not in existing_columns:
        op.add_column(
            "site_profile",
            sa.Column("hero_image_url", sa.String(length=500), nullable=False, server_default=""),
        )

    if "hero_poster_url" not in existing_columns:
        op.add_column(
            "site_profile",
            sa.Column("hero_poster_url", sa.String(length=500), nullable=False, server_default=""),
        )


def downgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.drop_column("hero_poster_url")
        batch_op.drop_column("hero_image_url")
