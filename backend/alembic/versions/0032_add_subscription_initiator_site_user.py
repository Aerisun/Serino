"""add subscription initiator site user

Revision ID: 0032_add_subscription_initiator_site_user
Revises: 0031_add_webhook_subscription_test_status
Create Date: 2026-03-29 01:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0032_add_subscription_initiator_site_user"
down_revision = "0031_add_webhook_subscription_test_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("content_subscribers")}
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("content_subscribers")}

    if "initiator_site_user_id" not in columns:
        with op.batch_alter_table("content_subscribers") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "initiator_site_user_id",
                    sa.String(length=36),
                    nullable=True,
                )
            )

    if "fk_content_subscribers_initiator_site_user_id" not in foreign_keys:
        with op.batch_alter_table("content_subscribers") as batch_op:
            batch_op.create_foreign_key(
                "fk_content_subscribers_initiator_site_user_id",
                "site_users",
                ["initiator_site_user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    inspector = inspect(connection)
    indexes = {index["name"] for index in inspector.get_indexes("content_subscribers")}
    if "ix_content_subscribers_initiator_site_user_id" not in indexes:
        op.create_index(
            "ix_content_subscribers_initiator_site_user_id",
            "content_subscribers",
            ["initiator_site_user_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_content_subscribers_initiator_site_user_id", table_name="content_subscribers")
    with op.batch_alter_table("content_subscribers") as batch_op:
        batch_op.drop_constraint("fk_content_subscribers_initiator_site_user_id", type_="foreignkey")
        batch_op.drop_column("initiator_site_user_id")
