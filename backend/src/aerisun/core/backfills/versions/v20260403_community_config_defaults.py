from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.seed import backfill_community_config_defaults

migration_key = "20260403_community_config_defaults"
summary = "归一化社区评论配置并补齐评论面板默认入口"
resource_keys = ("site.community",)


def apply(session: Session) -> None:
    backfill_community_config_defaults(session)
