"""add subscription delivery logs and advanced templates

Revision ID: 0030_add_subscription_delivery_and_templates
Revises: 0029_add_subscription_smtp_test_status
Create Date: 2026-03-28 23:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0030_add_subscription_delivery_and_templates"
down_revision = "0029_add_subscription_smtp_test_status"
branch_labels = None
depends_on = None

DEFAULT_SUBJECT_TEMPLATE = "[{site_name}] {content_title}"
DEFAULT_BODY_TEMPLATE = (
    "{site_name} 有新的{content_type_label}内容发布。\n\n"
    "{content_title}\n"
    "{content_summary}\n\n"
    "阅读链接：{content_url}\n"
    "RSS：{feed_url}"
)
DEFAULT_ALLOWED_CONTENT_TYPES_JSON = '["posts", "diary", "thoughts", "excerpts"]'


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    if inspector.has_table("_alembic_tmp_content_subscription_config"):
        op.drop_table("_alembic_tmp_content_subscription_config")
        inspector = inspect(connection)
    config_columns = {column["name"] for column in inspector.get_columns("content_subscription_config")}

    if {
        "allowed_content_types",
        "mail_subject_template",
        "mail_body_template",
    } - config_columns:
        with op.batch_alter_table("content_subscription_config") as batch_op:
            if "allowed_content_types" not in config_columns:
                batch_op.add_column(
                    sa.Column(
                        "allowed_content_types",
                        sa.JSON(),
                        nullable=False,
                        server_default=sa.text("'[]'"),
                    )
                )
            if "mail_subject_template" not in config_columns:
                batch_op.add_column(
                    sa.Column(
                        "mail_subject_template",
                        sa.String(length=255),
                        nullable=False,
                        server_default=DEFAULT_SUBJECT_TEMPLATE,
                    )
                )
            if "mail_body_template" not in config_columns:
                batch_op.add_column(
                    sa.Column(
                        "mail_body_template",
                        sa.Text(),
                        nullable=False,
                        server_default=DEFAULT_BODY_TEMPLATE,
                    )
                )

    config_columns = {column["name"] for column in inspect(connection).get_columns("content_subscription_config")}
    if {
        "allowed_content_types",
        "mail_subject_template",
        "mail_body_template",
    } <= config_columns:
        connection.execute(
            sa.text(
                """
                UPDATE content_subscription_config
                SET
                    allowed_content_types = :allowed_content_types,
                    mail_subject_template = :mail_subject_template,
                    mail_body_template = :mail_body_template
                """
            ),
            {
                "allowed_content_types": DEFAULT_ALLOWED_CONTENT_TYPES_JSON,
                "mail_subject_template": DEFAULT_SUBJECT_TEMPLATE,
                "mail_body_template": DEFAULT_BODY_TEMPLATE,
            },
        )

    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    if "content_notification_deliveries" not in existing_tables:
        op.create_table(
            "content_notification_deliveries",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("notification_id", sa.String(length=36), nullable=False),
            sa.Column("subscriber_email", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=32), nullable=False),
            sa.Column("content_slug", sa.String(length=160), nullable=False),
            sa.Column("content_title", sa.String(length=240), nullable=False),
            sa.Column("content_url", sa.String(length=500), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="sent"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        existing_tables.add("content_notification_deliveries")

    inspector = inspect(connection)
    if "content_notification_deliveries" in existing_tables:
        if not _has_index(
            inspector,
            "content_notification_deliveries",
            "ix_content_notification_deliveries_subscriber_email",
        ):
            op.create_index(
                "ix_content_notification_deliveries_subscriber_email",
                "content_notification_deliveries",
                ["subscriber_email"],
            )
        if not _has_index(
            inspector,
            "content_notification_deliveries",
            "ix_content_notification_deliveries_notification_id",
        ):
            op.create_index(
                "ix_content_notification_deliveries_notification_id",
                "content_notification_deliveries",
                ["notification_id"],
            )


def downgrade() -> None:
    op.drop_index("ix_content_notification_deliveries_notification_id", table_name="content_notification_deliveries")
    op.drop_index("ix_content_notification_deliveries_subscriber_email", table_name="content_notification_deliveries")
    op.drop_table("content_notification_deliveries")

    with op.batch_alter_table("content_subscription_config") as batch_op:
        batch_op.drop_column("mail_body_template")
        batch_op.drop_column("mail_subject_template")
        batch_op.drop_column("allowed_content_types")
