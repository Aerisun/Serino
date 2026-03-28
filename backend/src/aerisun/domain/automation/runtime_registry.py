from __future__ import annotations

from functools import lru_cache

from aerisun.core.settings import get_settings
from aerisun.domain.automation.runtime import AutomationRuntime


@lru_cache(maxsize=1)
def get_automation_runtime() -> AutomationRuntime:
    settings = get_settings()
    return AutomationRuntime(checkpoint_path=settings.workflow_db_path)
