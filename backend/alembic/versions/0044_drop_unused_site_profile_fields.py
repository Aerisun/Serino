"""Drop unused site_profile fields.

Remove deprecated footer and SEO duplicate fields now that the site owner
name and bio are the only canonical sources for those values.

Revision ID: 0044_drop_unused_site_profile_fields
Revises: 0043_add_backup_max_retention_count
Create Date: 2026-04-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0044_drop_unused_site_profile_fields"
down_revision = "0043_add_backup_max_retention_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {col["name"] for col in inspector.get_columns("site_profile")}

    with op.batch_alter_table("site_profile") as batch_op:
        for column_name in ("footer_text", "author", "meta_description", "copyright"):
            if column_name in columns:
                batch_op.drop_column(column_name)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {col["name"] for col in inspector.get_columns("site_profile")}

    with op.batch_alter_table("site_profile") as batch_op:
        if "footer_text" not in columns:
            batch_op.add_column(sa.Column("footer_text", sa.Text(), nullable=False, server_default=""))
        if "author" not in columns:
            batch_op.add_column(sa.Column("author", sa.String(120), nullable=False, server_default=""))
        if "meta_description" not in columns:
            batch_op.add_column(sa.Column("meta_description", sa.Text(), nullable=False, server_default=""))
        if "copyright" not in columns:
            batch_op.add_column(
                sa.Column("copyright", sa.String(200), nullable=False, server_default="All rights reserved")
            )
