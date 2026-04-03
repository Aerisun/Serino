from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.seed import backfill_page_copy_defaults

migration_key = "20260403_page_copy_defaults"
summary = "补齐页面文案默认值并修正已知历史副本"
resource_keys = ("site.pages",)


def apply(session: Session) -> None:
    backfill_page_copy_defaults(session)
