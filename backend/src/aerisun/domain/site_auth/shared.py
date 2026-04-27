from __future__ import annotations

from urllib.parse import urlsplit

ALLOWED_OAUTH_PROVIDERS = {"google", "github"}
ALLOWED_ADMIN_AUTH_METHODS = {"email", "google", "github"}


def normalize_email(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def normalize_display_name(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def normalize_return_to(value: str | None) -> str:
    candidate = (value or "/").strip() or "/"
    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc or not parts.path.startswith("/"):
        return "/"
    return candidate


def normalize_string_list(values: list[str] | None, allowed: set[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in values or []:
        item = str(raw or "").strip().lower()
        if not item or item not in allowed or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized
