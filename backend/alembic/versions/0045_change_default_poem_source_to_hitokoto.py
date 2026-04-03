"""Change default poem_source to hitokoto.

Revision ID: 0045_change_default_poem_source_to_hitokoto
Revises: 0044_drop_unused_site_profile_fields
Create Date: 2026-04-03
"""

from __future__ import annotations

from alembic import op

revision = "0045_change_default_poem_source_to_hitokoto"
down_revision = "0044_drop_unused_site_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.alter_column("poem_source", server_default="hitokoto")


def downgrade() -> None:
    with op.batch_alter_table("site_profile") as batch_op:
        batch_op.alter_column("poem_source", server_default="custom")
