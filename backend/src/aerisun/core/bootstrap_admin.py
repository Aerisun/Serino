from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.iam.bootstrap import ensure_default_production_admin


def ensure_first_boot_default_admin(*, is_first_boot: bool) -> bool:
    settings = get_settings()
    session_factory = get_session_factory()
    with session_factory() as session:
        user = ensure_default_production_admin(
            session,
            environment=settings.environment,
            is_first_boot=is_first_boot,
        )
    return user is not None
