"""add hero image and poster urls

Revision ID: 0016_add_hero_image_fields
Revises: 0015_add_asset_note
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_add_hero_image_fields"
down_revision = "0015_add_asset_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.add_column(sa.Column("hero_image_url", sa.String(length=500), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("hero_poster_url", sa.String(length=500), nullable=False, server_default=""))

    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.alter_column("hero_image_url", server_default=None)
        batch_op.alter_column("hero_poster_url", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.drop_column("hero_poster_url")
        batch_op.drop_column("hero_image_url")