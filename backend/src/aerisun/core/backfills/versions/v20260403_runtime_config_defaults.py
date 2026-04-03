from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.seed import backfill_runtime_config_defaults

migration_key = "20260403_runtime_config_defaults"
summary = "补齐站点登录、订阅与自动化模型配置默认项"
resource_keys = ("visitors.auth", "subscriptions.config", "automation.model_config")


def apply(session: Session) -> None:
    backfill_runtime_config_defaults(session)
