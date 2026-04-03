"""Drop unused page config fields and display options.

Revision ID: 0047_drop_unused_page_config_fields
Revises: 0046_drop_unused_resume_structures
Create Date: 2026-04-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0047_drop_unused_page_config_fields"
down_revision = "0046_drop_unused_resume_structures"
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
        page_copy = sa.table(
            "page_copy",
            sa.column("id", sa.String()),
            sa.column("page_key", sa.String()),
            sa.column("max_width", sa.String()),
            sa.column("extras", sa.JSON()),
        )
        dead_extra_keys_by_page = {
            "activity": {"heatmapLoadingLabel", "heatmapErrorLabel", "heatmapTotalTemplate"},
            "friends": {"statusLabel"},
            "guestbook": {
                "promptTitle",
                "nameFieldLabel",
                "contentFieldLabel",
                "submitFieldLabel",
                "namePlaceholder",
            },
        }
        rows = conn.execute(sa.select(page_copy.c.id, page_copy.c.page_key, page_copy.c.max_width, page_copy.c.extras)).fetchall()
        for row in rows:
            next_extras = dict(row.extras or {})
            dead_keys = dead_extra_keys_by_page.get(row.page_key, set())
            changed = False
            for key in dead_keys:
                if key in next_extras:
                    del next_extras[key]
                    changed = True

            next_values: dict[str, object] = {}
            if changed:
                next_values["extras"] = next_extras
            if row.page_key in {"activity", "notFound"} and row.max_width is not None:
                next_values["max_width"] = None
            if next_values:
                conn.execute(
                    page_copy.update().where(page_copy.c.id == row.id).values(**next_values)
                )

        columns = _column_names(inspector, "page_copy")
        with op.batch_alter_table("page_copy") as batch_op:
            for column_name in ("label", "nav_label", "description", "download_label"):
                if column_name in columns:
                    batch_op.drop_column(column_name)

    if "page_display_options" in table_names:
        op.drop_table("page_display_options")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = _table_names(inspector)

    if "page_copy" in table_names:
        columns = _column_names(inspector, "page_copy")
        with op.batch_alter_table("page_copy") as batch_op:
            if "label" not in columns:
                batch_op.add_column(sa.Column("label", sa.String(length=80), nullable=True))
            if "nav_label" not in columns:
                batch_op.add_column(sa.Column("nav_label", sa.String(length=80), nullable=True))
            if "description" not in columns:
                batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
            if "download_label" not in columns:
                batch_op.add_column(sa.Column("download_label", sa.String(length=80), nullable=True))

    if "page_display_options" not in table_names:
        op.create_table(
            "page_display_options",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("page_key", sa.String(length=80), nullable=False, unique=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
