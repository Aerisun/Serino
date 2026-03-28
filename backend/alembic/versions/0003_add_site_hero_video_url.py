"""Add hero_video_url to site_profile."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003_add_site_hero_video_url"
down_revision = "0002_add_site_meta_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    site_profile_columns = {column["name"] for column in inspector.get_columns("site_profile")}

    if "hero_video_url" in site_profile_columns:
        return

    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.add_column(sa.Column("hero_video_url", sa.String(500), nullable=True))


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    site_profile_columns = {column["name"] for column in inspector.get_columns("site_profile")}

    if "hero_video_url" not in site_profile_columns:
        return

    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.drop_column("hero_video_url")
