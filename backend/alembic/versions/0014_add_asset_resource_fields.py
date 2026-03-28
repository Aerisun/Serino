"""add asset resource fields

Revision ID: 0014_add_asset_resource_fields
Revises: 0013_add_site_poem_keywords
Create Date: 2026-03-25
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0014_add_asset_resource_fields"
down_revision = "0013_add_site_poem_keywords"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "assets" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("assets")}

    if "resource_key" not in existing_columns:
        op.add_column("assets", sa.Column("resource_key", sa.String(length=500), nullable=True))

    if "visibility" not in existing_columns:
        op.add_column(
            "assets",
            sa.Column(
                "visibility",
                sa.String(length=32),
                nullable=False,
                server_default="internal",
            ),
        )

    if "category" not in existing_columns:
        op.add_column(
            "assets",
            sa.Column(
                "category",
                sa.String(length=80),
                nullable=False,
                server_default="general",
            ),
        )

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, file_name, storage_path, sha256 FROM assets")).mappings().all()
    for row in rows:
        file_name = row["file_name"] or "upload"
        suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "bin"
        digest = (row["sha256"] or row["id"].replace("-", ""))[:12]
        resource_key = f"internal/assets/general/{digest}.{suffix}"
        connection.execute(
            sa.text("UPDATE assets SET resource_key = :resource_key WHERE id = :id"),
            {"resource_key": resource_key, "id": row["id"]},
        )

        storage_path = row["storage_path"]
        if storage_path:
            src = Path(storage_path)
            if src.exists():
                dest = src.parents[3] / resource_key if len(src.parents) >= 4 else src.parent / resource_key
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    src.replace(dest)
                connection.execute(
                    sa.text("UPDATE assets SET storage_path = :storage_path WHERE id = :id"),
                    {"storage_path": str(dest), "id": row["id"]},
                )

    with op.batch_alter_table("assets") as batch_op:
        batch_op.alter_column("resource_key", nullable=False)
        batch_op.create_unique_constraint("uq_assets_resource_key", ["resource_key"])
        batch_op.alter_column("visibility", server_default=None)
        batch_op.alter_column("category", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_constraint("uq_assets_resource_key", type_="unique")
        batch_op.drop_column("category")
        batch_op.drop_column("visibility")
        batch_op.drop_column("resource_key")
