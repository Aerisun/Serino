"""Lightweight, privacy-aware enrichment helpers for visit records.

These mirror what mainstream open-source analytics (Plausible / Umami) extract
from a request without any third-party network call:

* ``parse_referer`` -> normalised referrer domain.
* ``parse_utm`` -> UTM campaign parameters from a URL query string.
* ``split_path_query`` -> separate the in-app path from its query string.
* ``compute_visitor_id`` -> a monthly-rotating, salted hash of ``ip + user_agent``.

The visitor id follows Plausible's approach (a random salt that is periodically
rotated so the value cannot be linked back to a person or correlated across
periods), but uses a *monthly* rotation window: the same visitor produces a
stable id for the whole calendar month, giving accurate per-month unique-visitor
counts (more robust than naive IP de-duplication behind NAT / mobile networks).
When the month rolls over the salt is regenerated and the old one discarded, so
historical hashes can no longer be recomputed.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from aerisun.core.time import shanghai_now

_UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
VisitPathKind = Literal["page", "system_resource", "ai_entry"]

_AI_ENTRY_EXACT_PATHS = {
    "/llms.txt",
    "/resume.md",
    "/feed.xml",
    "/rss.xml",
    "/feeds.xml",
}
_AI_ENTRY_PREFIXES = ("/feeds/",)
_SYSTEM_RESOURCE_EXACT_PATHS = {
    "/manifest.webmanifest",
    "/favicon.ico",
    "/bootstrap.js",
    "/robots.txt",
    "/sitemap.xml",
    "/mcp/install",
}
_SYSTEM_RESOURCE_PREFIXES = ("/assets/", "/favicon", "/mcp/install/")
_SYSTEM_RESOURCE_EXTENSIONS = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".avif",
    ".map",
    ".json",
    ".txt",
    ".xml",
    ".webmanifest",
    ".woff",
    ".woff2",
    ".ttf",
)


@dataclass(slots=True, frozen=True)
class UtmParams:
    source: str | None = None
    medium: str | None = None
    campaign: str | None = None
    term: str | None = None
    content: str | None = None


def split_path_query(raw: str | None) -> tuple[str, str | None]:
    """Split a possibly absolute URL/path into ``(path, query)``."""

    if not raw:
        return "/", None
    parts = urlsplit(raw.strip())
    path = parts.path or "/"
    if not path.startswith("/"):
        path = "/" + path
    query = parts.query or None
    return path, query


def _normalized_visit_path(raw: str | None) -> str:
    path, _ = split_path_query(raw)
    return path


def classify_visit_path(raw: str | None) -> VisitPathKind:
    """Classify a request path for public page-view analytics.

    ``page`` is a user-facing page view. Other categories are useful signals,
    but they are not "which page did a human visitor read" analytics.
    """

    path = _normalized_visit_path(raw)
    lowered = path.lower()
    exact_path = lowered.rstrip("/") if lowered != "/" else lowered
    if exact_path in _AI_ENTRY_EXACT_PATHS or any(lowered.startswith(prefix) for prefix in _AI_ENTRY_PREFIXES):
        return "ai_entry"
    if (
        exact_path in _SYSTEM_RESOURCE_EXACT_PATHS
        or any(lowered.startswith(prefix) for prefix in _SYSTEM_RESOURCE_PREFIXES)
        or lowered.endswith(_SYSTEM_RESOURCE_EXTENSIONS)
    ):
        return "system_resource"
    return "page"


def is_trackable_page_visit_path(raw: str | None) -> bool:
    return classify_visit_path(raw) == "page"


def parse_referer(referer: str | None, *, current_host: str | None = None) -> str | None:
    """Return the normalised referrer domain (``www.`` stripped).

    Same-host referrers are treated as internal navigation and dropped so the
    "external sources" view is not polluted by in-site clicks.
    """

    if not referer:
        return None
    host = urlsplit(referer.strip()).netloc.lower()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    if current_host:
        normalized_current = current_host.lower()
        if normalized_current.startswith("www."):
            normalized_current = normalized_current[4:]
        if host == normalized_current:
            return None
    return host or None


def parse_utm(query: str | None) -> UtmParams:
    if not query:
        return UtmParams()
    parsed = parse_qs(query, keep_blank_values=False)

    def _first(key: str) -> str | None:
        values = parsed.get(key)
        if not values:
            return None
        value = values[0].strip()
        return value[:128] or None

    return UtmParams(
        source=_first("utm_source"),
        medium=_first("utm_medium"),
        campaign=_first("utm_campaign"),
        term=_first("utm_term"),
        content=_first("utm_content"),
    )


def _current_period() -> str:
    """Return the active rotation window key (``YYYY-MM``)."""

    return shanghai_now().strftime("%Y-%m")


_current_salt: str = secrets.token_hex(16)
_current_salt_period: str = _current_period()


def _period_salt() -> str:
    """Return this month's salt, rotating it when the calendar month changes."""

    global _current_salt, _current_salt_period
    period = _current_period()
    if period != _current_salt_period:
        _current_salt = secrets.token_hex(16)
        _current_salt_period = period
    return _current_salt


def compute_visitor_id(ip_address: str | None, user_agent: str | None) -> str:
    """Monthly-rotating, salted visitor fingerprint (not personally identifying)."""

    salt = _period_salt()
    raw = f"{salt}|{_current_salt_period}|{(ip_address or '').strip()}|{(user_agent or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
