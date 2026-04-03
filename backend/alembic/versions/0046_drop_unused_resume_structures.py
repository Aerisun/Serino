"""Drop unused resume structures and stale page config.

Revision ID: 0046_drop_unused_resume_structures
Revises: 0045_change_default_poem_source_to_hitokoto
Create Date: 2026-04-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0046_drop_unused_resume_structures"
down_revision = "0045_change_default_poem_source_to_hitokoto"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = _table_names(inspector)

    if "page_copy" in table_names:
        op.execute(sa.text("DELETE FROM page_copy WHERE page_key = 'resume'"))
    if "page_display_options" in table_names:
        op.execute(sa.text("DELETE FROM page_display_options WHERE page_key = 'resume'"))

    if "resume_experiences" in table_names:
        op.drop_table("resume_experiences")
    if "resume_skills" in table_names:
        op.drop_table("resume_skills")

    if "resume_basics" not in table_names:
        return

    columns = _column_names(inspector, "resume_basics")
    with op.batch_alter_table("resume_basics") as batch_op:
        for column_name in (
            "subtitle",
            "download_label",
            "template_key",
            "accent_tone",
            "availability",
            "website",
            "highlights",
        ):
            if column_name in columns:
                batch_op.drop_column(column_name)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = _table_names(inspector)

    if "resume_basics" in table_names:
        columns = _column_names(inspector, "resume_basics")
        with op.batch_alter_table("resume_basics") as batch_op:
            if "subtitle" not in columns:
                batch_op.add_column(sa.Column("subtitle", sa.String(length=160), nullable=False, server_default=""))
            if "download_label" not in columns:
                batch_op.add_column(
                    sa.Column("download_label", sa.String(length=80), nullable=False, server_default="")
                )
            if "template_key" not in columns:
                batch_op.add_column(
                    sa.Column("template_key", sa.String(length=80), nullable=False, server_default="editorial")
                )
            if "accent_tone" not in columns:
                batch_op.add_column(
                    sa.Column("accent_tone", sa.String(length=80), nullable=False, server_default="amber")
                )
            if "availability" not in columns:
                batch_op.add_column(
                    sa.Column("availability", sa.String(length=160), nullable=False, server_default="")
                )
            if "website" not in columns:
                batch_op.add_column(sa.Column("website", sa.String(length=255), nullable=False, server_default=""))
            if "highlights" not in columns:
                batch_op.add_column(sa.Column("highlights", sa.JSON(), nullable=False, server_default="[]"))

    if "resume_skills" not in table_names:
        op.create_table(
            "resume_skills",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("resume_basics_id", sa.String(length=36), sa.ForeignKey("resume_basics.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category", sa.String(length=120), nullable=False),
            sa.Column("items", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "resume_experiences" not in table_names:
        op.create_table(
            "resume_experiences",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("resume_basics_id", sa.String(length=36), sa.ForeignKey("resume_basics.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("company", sa.String(length=160), nullable=False),
            sa.Column("period", sa.String(length=120), nullable=False),
            sa.Column("location", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("employment_type", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("achievements", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("tech_stack", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "page_copy" in table_names:
        op.execute(
            sa.text(
                """
                INSERT INTO page_copy (
                    id,
                    page_key,
                    label,
                    nav_label,
                    title,
                    subtitle,
                    description,
                    search_placeholder,
                    empty_message,
                    max_width,
                    page_size,
                    download_label,
                    extras,
                    created_at,
                    updated_at
                )
                SELECT
                    lower(hex(randomblob(16))),
                    'resume',
                    NULL,
                    '简历',
                    'Felix',
                    'UI/UX Designer · Frontend Developer',
                    '简历页配置。',
                    NULL,
                    NULL,
                    'max-w-3xl',
                    NULL,
                    NULL,
                    '{}',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                WHERE NOT EXISTS (SELECT 1 FROM page_copy WHERE page_key = 'resume')
                """
            )
        )

    if "page_display_options" in table_names:
        op.execute(
            sa.text(
                """
                INSERT INTO page_display_options (id, page_key, is_enabled, settings, created_at, updated_at)
                SELECT
                    lower(hex(randomblob(16))),
                    'resume',
                    1,
                    '{"show_download": true}',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                WHERE NOT EXISTS (SELECT 1 FROM page_display_options WHERE page_key = 'resume')
                """
            )
        )
