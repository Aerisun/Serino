"""Add comment feedback email configuration.

Revision ID: 0007_comment_feedback_config
Revises: 0006_visit_record_user_agent_fields
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0007_comment_feedback_config"
down_revision = "0006_visit_record_user_agent_fields"
branch_labels = None
depends_on = None

TABLE = "content_subscription_config"
NEW_COLUMNS = (
    ("comment_feedback_enabled", sa.Boolean(), False),
    ("comment_feedback_subject_template", sa.String(length=255), "[{site_name}] {reply_author_name} 回复了你的评论"),
    (
        "comment_feedback_body_template",
        sa.Text(),
        (
            "{reply_author_name} 回复了你在 {site_name} 的评论。\n\n"
            "你的评论：\n{parent_comment}\n\n"
            "回复内容：\n{reply_content}\n\n"
            "查看回复：{comment_url}"
        ),
    ),
)


def _columns() -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if TABLE not in inspect(op.get_bind()).get_table_names():
        return
    existing = _columns()
    for name, column_type, default in NEW_COLUMNS:
        if name in existing:
            continue
        op.add_column(TABLE, sa.Column(name, column_type, nullable=True))
        op.execute(sa.text(f"UPDATE {TABLE} SET {name} = :default WHERE {name} IS NULL").bindparams(default=default))


def downgrade() -> None:
    if TABLE not in inspect(op.get_bind()).get_table_names():
        return
    existing = _columns()
    for name, _, _ in reversed(NEW_COLUMNS):
        if name in existing:
            op.drop_column(TABLE, name)
