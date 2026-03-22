from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)

RATE_WRITE_ENGAGEMENT = "5/minute"
RATE_WRITE_REACTION = "10/minute"
RATE_AUTH_LOGIN = "10/minute"
