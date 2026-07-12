"""Anchor the persistent content view-count backfill.

Revision ID: 0014_persist_content_view_counts
Revises: 0013_asset_public_slug
Create Date: 2026-07-12
"""

from __future__ import annotations

revision = "0014_persist_content_view_counts"
down_revision = "0013_asset_public_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """The accompanying data migration persists existing view totals."""


def downgrade() -> None:
    """View totals are data and must remain intact when downgrading schema."""
