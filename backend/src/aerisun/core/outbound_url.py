"""Lightweight outbound destination policy for user-configured HTTP callbacks."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from aerisun.domain.exceptions import ValidationError

_WEBHOOK_SCHEMES = frozenset({"http", "https"})
_SAFE_PRIVILEGED_PORTS = frozenset({80, 443})
_PRIVATE_HOST_SUFFIXES = (".internal", ".lan", ".local", ".localhost", ".home")
_ALWAYS_BLOCKED_HOSTS = frozenset(
    {
        "metadata.amazonaws.com",
        "metadata.google.internal",
    }
)
_AMBIGUOUS_NUMERIC_HOST = re.compile(r"(?i)^(?:0x[0-9a-f]+|[0-9.]+)$")


def _webhook_url_error(detail: str) -> ValidationError:
    return ValidationError(f"Webhook target URL {detail}")


def validate_webhook_target_url(
    value: str,
    *,
    allow_private_network: bool = False,
) -> str:
    """Validate a webhook URL before storage and immediately before dispatch."""

    normalized = str(value or "").strip()
    if not normalized:
        raise _webhook_url_error("is required")
    if len(normalized) > 500:
        raise _webhook_url_error("must be at most 500 characters")
    if any(ord(character) < 32 for character in normalized) or "\\" in normalized:
        raise _webhook_url_error("contains invalid characters")

    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise _webhook_url_error("is invalid") from exc

    if parsed.scheme.lower() not in _WEBHOOK_SCHEMES:
        raise _webhook_url_error("must use http or https")
    if not parsed.netloc or not parsed.hostname:
        raise _webhook_url_error("must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise _webhook_url_error("must not include credentials")
    if parsed.fragment:
        raise _webhook_url_error("must not include a fragment")
    if port is not None and (port <= 0 or (port < 1024 and port not in _SAFE_PRIVILEGED_PORTS)):
        raise _webhook_url_error("uses a disallowed port")

    raw_hostname = parsed.hostname.rstrip(".").lower()
    if not raw_hostname or "%" in raw_hostname:
        raise _webhook_url_error("contains an invalid host")
    try:
        hostname = raw_hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise _webhook_url_error("contains an invalid host") from exc

    if hostname in _ALWAYS_BLOCKED_HOSTS:
        raise _webhook_url_error("points to a metadata service")
    if hostname == "localhost" or hostname.endswith(_PRIVATE_HOST_SUFFIXES):
        if not allow_private_network:
            raise _webhook_url_error("points to a private network; explicit opt-in is required")
        return normalized

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if _AMBIGUOUS_NUMERIC_HOST.fullmatch(hostname):
            raise _webhook_url_error("contains an ambiguous numeric host") from None
        return normalized

    if address.is_link_local or address.is_unspecified or address.is_multicast or address.is_reserved:
        raise _webhook_url_error("points to a reserved or link-local address")
    if address.is_loopback or address.is_private:
        if not allow_private_network:
            raise _webhook_url_error("points to a private network; explicit opt-in is required")
        return normalized
    if not address.is_global:
        raise _webhook_url_error("does not point to a public address")
    return normalized
