"""Add site meta fields and page nav_label.

- site_profile: author, og_image, meta_description, copyright, hero_actions
- page_copy: nav_label
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002_add_site_meta_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    site_profile_columns = {column["name"] for column in inspector.get_columns("site_profile")}
    page_copy_columns = {column["name"] for column in inspector.get_columns("page_copy")}

    with op.batch_alter_table("site_profile") as batch_op:
        if "author" not in site_profile_columns:
            batch_op.add_column(sa.Column("author", sa.String(120), nullable=False, server_default=""))
        if "og_image" not in site_profile_columns:
            batch_op.add_column(sa.Column("og_image", sa.String(500), nullable=False, server_default="/images/hero_bg.jpeg"))
        if "meta_description" not in site_profile_columns:
            batch_op.add_column(sa.Column("meta_description", sa.Text(), nullable=False, server_default=""))
        if "copyright" not in site_profile_columns:
            batch_op.add_column(sa.Column("copyright", sa.String(200), nullable=False, server_default="All rights reserved"))
        if "hero_actions" not in site_profile_columns:
            batch_op.add_column(sa.Column("hero_actions", sa.Text(), nullable=False, server_default="[]"))

    with op.batch_alter_table("page_copy") as batch_op:
        if "nav_label" not in page_copy_columns:
            batch_op.add_column(sa.Column("nav_label", sa.String(80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("page_copy") as batch_op:
        batch_op.drop_column("nav_label")

    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.drop_column("hero_actions")
        batch_op.drop_column("copyright")
        batch_op.drop_column("meta_description")
        batch_op.drop_column("og_image")
        batch_op.drop_column("author")
