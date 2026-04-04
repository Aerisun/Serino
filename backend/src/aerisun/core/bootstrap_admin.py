from __future__ import annotations

import base64
import os

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.iam.bootstrap import ensure_default_production_admin

BOOTSTRAP_ADMIN_USERNAME_ENV = "AERISUN_BOOTSTRAP_ADMIN_USERNAME"
BOOTSTRAP_ADMIN_PASSWORD_ENV = "AERISUN_BOOTSTRAP_ADMIN_PASSWORD"
BOOTSTRAP_ADMIN_USERNAME_B64_ENV = "AERISUN_BOOTSTRAP_ADMIN_USERNAME_B64"
BOOTSTRAP_ADMIN_PASSWORD_B64_ENV = "AERISUN_BOOTSTRAP_ADMIN_PASSWORD_B64"


def _decode_b64_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        return ""
    return base64.b64decode(value.encode("utf-8")).decode("utf-8")


def _resolve_bootstrap_admin_credentials() -> tuple[str, str] | tuple[None, None]:
    username = (
        _decode_b64_env(BOOTSTRAP_ADMIN_USERNAME_B64_ENV) or os.environ.get(BOOTSTRAP_ADMIN_USERNAME_ENV, "").strip()
    )
    password = _decode_b64_env(BOOTSTRAP_ADMIN_PASSWORD_B64_ENV) or os.environ.get(BOOTSTRAP_ADMIN_PASSWORD_ENV, "")

    if not username and not password:
        return None, None
    if not username or not password:
        raise RuntimeError("Incomplete bootstrap admin credentials for first production boot")
    return username, password


def ensure_first_boot_default_admin(*, is_first_boot: bool) -> bool:
    settings = get_settings()
    username, password = _resolve_bootstrap_admin_credentials()
    session_factory = get_session_factory()
    with session_factory() as session:
        user = ensure_default_production_admin(
            session,
            environment=settings.environment,
            is_first_boot=is_first_boot,
            username=username,
            password=password,
        )
    return user is not None
