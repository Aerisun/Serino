"""Expand resume configuration and experience fields

Revision ID: 0011_expand_resume_configuration
Revises: 0010_add_traffic_daily_snapshots
Create Date: 2026-03-25 20:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0011_expand_resume_configuration"
down_revision: Union[str, None] = "0010_add_traffic_daily_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("resume_basics"):
        for column_name, column in (
            (
                "template_key",
                sa.Column("template_key", sa.String(length=80), nullable=False, server_default="editorial"),
            ),
            ("accent_tone", sa.Column("accent_tone", sa.String(length=80), nullable=False, server_default="amber")),
            ("location", sa.Column("location", sa.String(length=160), nullable=False, server_default="")),
            ("availability", sa.Column("availability", sa.String(length=160), nullable=False, server_default="")),
            ("email", sa.Column("email", sa.String(length=160), nullable=False, server_default="")),
            ("website", sa.Column("website", sa.String(length=255), nullable=False, server_default="")),
            (
                "profile_image_url",
                sa.Column("profile_image_url", sa.String(length=500), nullable=False, server_default=""),
            ),
            ("highlights", sa.Column("highlights", sa.JSON(), nullable=False, server_default="[]")),
        ):
            if not _has_column(inspector, "resume_basics", column_name):
                op.add_column("resume_basics", column)

    inspector = inspect(bind)
    if inspector.has_table("resume_experiences"):
        for column_name, column in (
            ("location", sa.Column("location", sa.String(length=160), nullable=False, server_default="")),
            ("employment_type", sa.Column("employment_type", sa.String(length=80), nullable=False, server_default="")),
            ("achievements", sa.Column("achievements", sa.JSON(), nullable=False, server_default="[]")),
            ("tech_stack", sa.Column("tech_stack", sa.JSON(), nullable=False, server_default="[]")),
        ):
            if not _has_column(inspector, "resume_experiences", column_name):
                op.add_column("resume_experiences", column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("resume_experiences"):
        for column_name in ("tech_stack", "achievements", "employment_type", "location"):
            if _has_column(inspector, "resume_experiences", column_name):
                op.drop_column("resume_experiences", column_name)

    inspector = inspect(bind)
    if inspector.has_table("resume_basics"):
        for column_name in (
            "highlights",
            "profile_image_url",
            "website",
            "email",
            "availability",
            "location",
            "accent_tone",
            "template_key",
        ):
            if _has_column(inspector, "resume_basics", column_name):
                op.drop_column("resume_basics", column_name)
