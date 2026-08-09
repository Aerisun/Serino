"""Central, bounded redaction helpers for API, prompt, trace, and log payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel

REDACTED = "[redacted]"
CIRCULAR = "[circular]"
TRUNCATED = "[truncated]"
SECRET_ENVELOPE_PREFIX = "aerisun:enc:v1:"

_SENSITIVE_EXACT_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set_cookie",
        "client_secret",
        "private_key",
        "password",
        "passphrase",
        "secret",
        "smtp_password",
        "access_token",
        "refresh_token",
        "auth_token",
        "bot_token",
        "id_token",
        "webhook_token",
        "x_api_key",
    }
)
_SENSITIVE_SUFFIXES = ("_password", "_secret", "_api_key", "_access_token", "_refresh_token", "_auth_token")
_SAFE_TOKEN_KEYS = frozenset({"max_tokens", "token_count", "input_tokens", "output_tokens", "total_tokens"})
_URL_SECRET_QUERY_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "key",
        "secret",
        "signature",
        "sig",
        "token",
        "access_token",
        "auth",
        "authorization",
        "password",
    }
)
_BEARER_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|secret)\s*[:=]\s*([^\s,;]+)"
)
_TELEGRAM_BOT_PATH_RE = re.compile(r"(?i)/bot[^/]+")


def normalize_sensitive_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")


def is_sensitive_key(key: object) -> bool:
    normalized = normalize_sensitive_key(key)
    if not normalized or normalized in _SAFE_TOKEN_KEYS:
        return False
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    return normalized.endswith(_SENSITIVE_SUFFIXES)


def sanitize_url(value: str) -> str:
    """Remove credentials and secret-like query/path values while retaining destination context."""

    try:
        parsed = urlsplit(value)
    except ValueError:
        return _scrub_secret_text(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _scrub_secret_text(value)

    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    try:
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
    except ValueError:
        netloc = hostname

    query = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, REDACTED if normalize_sensitive_key(key) in _URL_SECRET_QUERY_KEYS else item))
    path = _TELEGRAM_BOT_PATH_RE.sub(f"/bot{REDACTED}", parsed.path)
    return urlunsplit((parsed.scheme, netloc, path, urlencode(query), parsed.fragment))


def _scrub_secret_text(value: str) -> str:
    scrubbed = _BEARER_RE.sub(lambda match: f"{match.group(1)} {REDACTED}", value)
    scrubbed = _ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", scrubbed)
    return _TELEGRAM_BOT_PATH_RE.sub(f"/bot{REDACTED}", scrubbed)


def _redact_string(value: str, *, max_string_length: int) -> str:
    if value.startswith(SECRET_ENVELOPE_PREFIX):
        return REDACTED
    value = sanitize_url(value) if value.startswith(("http://", "https://")) else _scrub_secret_text(value)
    if len(value) > max_string_length:
        return value[:max_string_length] + TRUNCATED
    return value


def redact_sensitive_data(
    value: Any,
    *,
    max_depth: int = 12,
    max_items: int = 500,
    max_string_length: int = 20_000,
) -> Any:
    """Return a non-mutating, JSON-friendly redacted projection with resource bounds."""

    seen: set[int] = set()

    def visit(item: Any, *, depth: int, parent_key: str = "") -> Any:
        if depth > max_depth:
            return TRUNCATED
        if item is None or isinstance(item, (bool, int, float)):
            return item
        if isinstance(item, str):
            return _redact_string(item, max_string_length=max_string_length)
        if isinstance(item, bytes):
            return f"[bytes:{len(item)}]"
        if isinstance(item, BaseModel):
            item = item.model_dump(mode="json")
        elif is_dataclass(item) and not isinstance(item, type):
            item = {field.name: getattr(item, field.name) for field in fields(item)}

        if isinstance(item, Mapping):
            identity = id(item)
            if identity in seen:
                return CIRCULAR
            seen.add(identity)
            try:
                output: dict[str, Any] = {}
                for index, (key, child) in enumerate(item.items()):
                    if index >= max_items:
                        output[TRUNCATED] = TRUNCATED
                        break
                    text_key = str(key)
                    if is_sensitive_key(text_key):
                        output[text_key] = REDACTED if child is not None and child != "" else child
                    else:
                        output[text_key] = visit(child, depth=depth + 1, parent_key=text_key)
                return output
            finally:
                seen.remove(identity)

        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            identity = id(item)
            if identity in seen:
                return CIRCULAR
            seen.add(identity)
            try:
                output = [visit(child, depth=depth + 1, parent_key=parent_key) for child in item[:max_items]]
                if len(item) > max_items:
                    output.append(TRUNCATED)
                return output
            finally:
                seen.remove(identity)

        return _redact_string(str(item), max_string_length=max_string_length)

    return visit(value, depth=0)


def safe_exception_detail(error: BaseException | str, *, known_secrets: Sequence[str] = ()) -> str:
    detail = str(error)
    for secret in known_secrets:
        if secret:
            detail = detail.replace(secret, REDACTED)
    return _redact_string(detail, max_string_length=4_000)


def restore_redacted_placeholders(value: Any, original: Any) -> Any:
    """Merge a public round-trip payload without replacing stored secrets by the mask marker."""

    if value == REDACTED:
        return original
    if isinstance(value, Mapping) and isinstance(original, Mapping):
        return {str(key): restore_redacted_placeholders(item, original.get(key)) for key, item in value.items()}
    if isinstance(value, list) and isinstance(original, list):
        original_by_id = {
            str(item.get("id")): item for item in original if isinstance(item, Mapping) and item.get("id") is not None
        }
        merged: list[Any] = []
        for index, item in enumerate(value):
            fallback = original[index] if index < len(original) else None
            if isinstance(item, Mapping) and item.get("id") is not None:
                fallback = original_by_id.get(str(item.get("id")), fallback)
            merged.append(restore_redacted_placeholders(item, fallback))
        return merged
    return value
