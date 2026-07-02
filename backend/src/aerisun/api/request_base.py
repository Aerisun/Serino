from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request

from aerisun.core.settings import get_settings

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def public_base_url_from_request(request: Request) -> str:
    settings_url = (get_settings().site_url or "").strip().rstrip("/")
    parsed = urlparse(settings_url)
    if settings_url and parsed.hostname not in _LOCAL_HOSTS:
        return settings_url

    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = (
        (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc)
        .split(",")[0]
        .strip()
    )
    return f"{proto}://{host}".rstrip("/")
