"""Merge object storage and site auth migration heads.

Revision ID: 0050_merge_object_storage_and_site_auth_heads
Revises: 0046_add_object_storage_acceleration, 0049_reconcile_site_auth_schema_drift
Create Date: 2026-04-03
"""

from __future__ import annotations


revision = "0050_merge_object_storage_and_site_auth_heads"
down_revision = ("0046_add_object_storage_acceleration", "0049_reconcile_site_auth_schema_drift")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
