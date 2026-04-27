from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

DEFAULT_COMMENT_IMAGE_RATE_LIMIT_COUNT = 18
DEFAULT_COMMENT_IMAGE_RATE_LIMIT_WINDOW_MINUTES = 30

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    storage_uri="memory://",
)

RATE_WRITE_ENGAGEMENT = "5/minute"
RATE_WRITE_REACTION = "10/minute"
RATE_COMMENT_IMAGE_UPLOAD = (
    f"{DEFAULT_COMMENT_IMAGE_RATE_LIMIT_COUNT}/{DEFAULT_COMMENT_IMAGE_RATE_LIMIT_WINDOW_MINUTES} minute"
)
RATE_AUTH_LOGIN = "10/minute"
RATE_SEARCH = "30/minute"


def _positive_int(value: object, fallback: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def comment_image_upload_rate_limit() -> str:
    try:
        from aerisun.core.db import get_session_factory
        from aerisun.domain.site_config import repository as site_config_repo

        with get_session_factory()() as session:
            config = site_config_repo.find_community_config(session)
            count = _positive_int(
                getattr(config, "comment_image_rate_limit_count", None),
                DEFAULT_COMMENT_IMAGE_RATE_LIMIT_COUNT,
            )
            window_minutes = _positive_int(
                getattr(config, "comment_image_rate_limit_window_minutes", None),
                DEFAULT_COMMENT_IMAGE_RATE_LIMIT_WINDOW_MINUTES,
            )
    except Exception:
        count = DEFAULT_COMMENT_IMAGE_RATE_LIMIT_COUNT
        window_minutes = DEFAULT_COMMENT_IMAGE_RATE_LIMIT_WINDOW_MINUTES

    return f"{count}/{window_minutes} minute"
