from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.seed import backfill_system_asset_references

migration_key = "20260403_system_asset_references"
summary = "将站点默认资源字段归拢为系统资源引用"
resource_keys = ("site.profile",)


def apply(session: Session) -> None:
    backfill_system_asset_references(session)
