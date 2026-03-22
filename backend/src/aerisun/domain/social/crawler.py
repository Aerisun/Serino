"""RSS feed crawler for Friend Circle.

Core crawling logic ported from Friend-Circle-Lite
(https://github.com/willow-god/Friend-Circle-Lite).
Adapted to work with Aerisun's SQLAlchemy models and httpx.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from dateutil import parser as dateutil_parser
from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.core.base import utcnow
from aerisun.core.settings import Settings

if TYPE_CHECKING:
    from aerisun.domain.social.models import Friend, FriendFeedSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — ported from FCL/__init__.py & FCL/single_friend.py
# ---------------------------------------------------------------------------

POSSIBLE_FEEDS = [
    ("atom", "/atom.xml"),
    ("rss", "/rss.xml"),
    ("rss2", "/rss2.xml"),
    ("rss3", "/rss.php"),
    ("feed", "/feed"),
    ("feed2", "/feed.xml"),
    ("feed3", "/feed/"),
    ("feed4", "/feed.php"),
    ("index", "/index.xml"),
]


def _build_headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.feed_crawl_user_agent,
        "Accept": (
            "application/atom+xml, application/rss+xml, "
            "application/xml;q=0.9, */*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


# ---------------------------------------------------------------------------
# Time parsing — ported from FCL/utils/time.py:format_published_time()
# Returns datetime instead of string to match ORM column type.
# ---------------------------------------------------------------------------

_TIME_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S GMT",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def _parse_published_time(time_str: str) -> datetime | None:
    """Parse a time string from an RSS/Atom entry into a UTC datetime."""
    if not time_str:
        return None

    parsed: datetime | None = None

    # Try dateutil first (handles most formats)
    try:
        parsed = dateutil_parser.parse(time_str, fuzzy=True)
    except (ValueError, dateutil_parser.ParserError):
        # Fall back to explicit formats
        for fmt in _TIME_FORMATS:
            try:
                parsed = datetime.strptime(time_str, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        logger.warning("Cannot parse time string: %s", time_str)
        return None

    # Ensure timezone-aware, default to UTC
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)

    return parsed


# ---------------------------------------------------------------------------
# URL fixing — ported from FCL/utils/url.py:replace_non_domain()
# ---------------------------------------------------------------------------


def _replace_non_domain(link: str, blog_url: str) -> str:
    """Replace localhost/IP addresses in article links with the blog URL."""
    try:
        parsed = urlparse(link)
        if "localhost" in parsed.netloc or re.match(
            r"^\d{1,3}(\.\d{1,3}){3}$", parsed.netloc
        ):
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            return urljoin(blog_url.rstrip("/") + "/", path.lstrip("/"))
        return link
    except Exception:
        return link


# ---------------------------------------------------------------------------
# Feed auto-discovery — ported from FCL/single_friend.py:check_feed()
# ---------------------------------------------------------------------------


def _check_feed(
    blog_url: str,
    client: httpx.Client,
) -> tuple[str, str]:
    """Try common feed paths and return (feed_type, feed_url).

    Returns ('none', blog_url) if no feed is found.
    """
    for feed_type, path in POSSIBLE_FEEDS:
        feed_url = blog_url.rstrip("/") + path
        try:
            response = client.get(feed_url)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "").lower()
                if (
                    "xml" in content_type
                    or "rss" in content_type
                    or "atom" in content_type
                ):
                    return (feed_type, feed_url)
                # Check content itself
                text_head = response.text[:1000].lower()
                if (
                    "<rss" in text_head
                    or "<feed" in text_head
                    or "<rdf:rdf" in text_head
                ):
                    return (feed_type, feed_url)
        except httpx.HTTPError:
            continue

    logger.warning("Cannot find feed URL for %s", blog_url)
    return ("none", blog_url)


# ---------------------------------------------------------------------------
# Feed parsing — ported from FCL/single_friend.py:parse_feed()
# ---------------------------------------------------------------------------


def _parse_feed(
    url: str,
    client: httpx.Client,
    max_items: int,
    blog_url: str = "",
) -> list[dict[str, Any]]:
    """Fetch and parse an RSS/Atom feed, returning normalized entries."""
    try:
        response = client.get(url)
        response.encoding = response.charset_encoding or "utf-8"
        feed = feedparser.parse(response.text)
    except Exception as e:
        logger.error("Failed to fetch/parse feed %s: %s", url, e)
        return []

    entries: list[dict[str, Any]] = []

    for entry in feed.entries:
        # Title
        title = getattr(entry, "title", "") or "Untitled"
        title = title[:240]

        # Link
        link = getattr(entry, "link", "")
        if not link:
            continue  # Cannot deduplicate without a URL
        if blog_url:
            link = _replace_non_domain(link, blog_url)

        # Published time
        published_at: datetime | None = None
        if hasattr(entry, "published"):
            published_at = _parse_published_time(entry.published)
        elif hasattr(entry, "updated"):
            published_at = _parse_published_time(entry.updated)

        # Summary — strip HTML tags
        summary = getattr(entry, "summary", "") or ""
        if hasattr(entry, "content") and entry.content:
            summary = entry.content[0].get("value", summary)
        summary = re.sub(r"<[^>]+>", "", summary)[:500]

        entries.append(
            {
                "title": title,
                "url": link,
                "summary": summary or None,
                "published_at": published_at,
                "raw_payload": {
                    "title": title,
                    "link": link,
                    "published": str(published_at) if published_at else "",
                },
            }
        )

    # Sort by published time descending, then limit
    entries.sort(
        key=lambda x: x["published_at"] or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return entries[:max_items]


# ---------------------------------------------------------------------------
# Single-source crawl — adapted from FCL/single_friend.py:process_friend()
# ---------------------------------------------------------------------------


def crawl_single_source(
    session: Session,
    source: FriendFeedSource,
    friend: Friend,
    settings: Settings,
) -> dict[str, Any]:
    """Crawl one feed source. Returns a result summary dict."""
    from aerisun.domain.social.models import FriendFeedItem

    headers = _build_headers(settings)
    timeout = httpx.Timeout(
        connect=settings.feed_crawl_timeout_connect,
        read=settings.feed_crawl_timeout_read,
        write=10.0,
        pool=10.0,
    )

    result: dict[str, Any] = {
        "source_id": source.id,
        "friend_name": friend.name,
        "status": "ok",
        "inserted": 0,
        "feed_url_updated": False,
    }

    with httpx.Client(
        headers=headers, timeout=timeout, follow_redirects=True
    ) as client:
        # --- 1. Try fetching with ETag ---
        extra_headers: dict[str, str] = {}
        if source.etag:
            extra_headers["If-None-Match"] = source.etag

        feed_url = source.feed_url
        content: str | None = None
        new_etag: str | None = None
        fetch_error: str | None = None

        try:
            resp = client.get(feed_url, headers=extra_headers)
            if resp.status_code == 304:
                source.last_fetched_at = utcnow()
                source.last_error = None
                result["status"] = "not_modified"
                return result
            if resp.status_code == 200:
                content = resp.text
                new_etag = resp.headers.get("etag")
            else:
                fetch_error = f"HTTP {resp.status_code}"
        except httpx.HTTPError as e:
            fetch_error = str(e)

        # --- 2. Auto-discover if fetch failed ---
        if content is None and fetch_error:
            logger.info(
                "Feed fetch failed for %s (%s), trying auto-discovery on %s",
                friend.name,
                fetch_error,
                friend.url,
            )
            feed_type, discovered_url = _check_feed(friend.url, client)
            if feed_type != "none" and discovered_url != feed_url:
                try:
                    resp = client.get(discovered_url)
                    if resp.status_code == 200:
                        content = resp.text
                        new_etag = resp.headers.get("etag")
                        # Update the stored feed_url
                        source.feed_url = discovered_url
                        result["feed_url_updated"] = True
                        fetch_error = None
                        logger.info(
                            "Auto-discovered feed for %s: %s",
                            friend.name,
                            discovered_url,
                        )
                except httpx.HTTPError as e:
                    fetch_error = f"Discovery also failed: {e}"

        # --- 3. Handle persistent failure ---
        if content is None:
            source.last_fetched_at = utcnow()
            source.last_error = fetch_error
            result["status"] = "error"
            result["error"] = fetch_error
            return result

        # --- 4. Parse feed from already-fetched content ---
        try:
            feed = feedparser.parse(content)
        except Exception as e:
            source.last_fetched_at = utcnow()
            source.last_error = f"Parse error: {e}"
            result["status"] = "error"
            result["error"] = str(e)
            return result

        entries = []
        for entry in feed.entries:
            title = getattr(entry, "title", "") or "Untitled"
            title = title[:240]

            link = getattr(entry, "link", "")
            if not link:
                continue
            link = _replace_non_domain(link, friend.url)

            published_at: datetime | None = None
            if hasattr(entry, "published"):
                published_at = _parse_published_time(entry.published)
            elif hasattr(entry, "updated"):
                published_at = _parse_published_time(entry.updated)

            summary = getattr(entry, "summary", "") or ""
            if hasattr(entry, "content") and entry.content:
                summary = entry.content[0].get("value", summary)
            summary = re.sub(r"<[^>]+>", "", summary)[:500]

            entries.append(
                {
                    "title": title,
                    "url": link,
                    "summary": summary or None,
                    "published_at": published_at,
                    "raw_payload": {
                        "title": title,
                        "link": link,
                        "published": str(published_at) if published_at else "",
                    },
                }
            )

        # Sort and limit
        entries.sort(
            key=lambda x: x["published_at"] or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        entries = entries[: settings.feed_crawl_max_items_per_source]

        # Filter future articles (tolerance: 2 days)
        max_allowed = utcnow() + timedelta(days=2)
        entries = [
            e
            for e in entries
            if e["published_at"] is None or e["published_at"] <= max_allowed
        ]

        # --- 5. Deduplicate and persist ---
        existing_urls: set[str] = set(
            session.scalars(
                select(FriendFeedItem.url).where(FriendFeedItem.source_id == source.id)
            ).all()
        )

        new_items = []
        for entry in entries:
            if entry["url"] in existing_urls:
                continue
            new_items.append(
                FriendFeedItem(
                    source_id=source.id,
                    title=entry["title"],
                    url=entry["url"],
                    summary=entry["summary"],
                    published_at=entry["published_at"],
                    raw_payload=entry["raw_payload"],
                )
            )

        if new_items:
            session.add_all(new_items)

        # --- 6. Update source metadata ---
        source.last_fetched_at = utcnow()
        source.etag = new_etag
        source.last_error = None

        result["inserted"] = len(new_items)
        logger.info(
            "Crawled %s: %d new items (of %d parsed)",
            friend.name,
            len(new_items),
            len(entries),
        )

    return result


# ---------------------------------------------------------------------------
# Full crawl — adapted from FCL/all_friends.py:fetch_and_process_data()
# ---------------------------------------------------------------------------


def crawl_all_feeds(settings: Settings | None = None) -> dict[str, Any]:
    """Crawl all enabled feed sources sequentially.

    Creates its own DB session (safe for background thread use).
    """
    from aerisun.core.db import get_session_factory
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.models import Friend, FriendFeedSource

    if settings is None:
        settings = get_settings()

    factory = get_session_factory()
    session = factory()

    results: list[dict[str, Any]] = []
    total_inserted = 0
    errors = 0

    try:
        sources = session.execute(
            select(FriendFeedSource, Friend)
            .join(Friend, FriendFeedSource.friend_id == Friend.id)
            .where(FriendFeedSource.is_enabled.is_(True))
            .where(Friend.status == "active")
        ).all()

        logger.info("Starting feed crawl: %d sources", len(sources))

        for source, friend in sources:
            try:
                result = crawl_single_source(session, source, friend, settings)
                session.commit()
                results.append(result)
                total_inserted += result.get("inserted", 0)
                if result.get("status") == "error":
                    errors += 1
            except Exception:
                logger.exception(
                    "Error crawling source %s (%s)", source.id, source.feed_url
                )
                session.rollback()
                errors += 1
                results.append(
                    {
                        "source_id": source.id,
                        "friend_name": friend.name,
                        "status": "error",
                        "error": "unexpected exception",
                    }
                )

        logger.info(
            "Feed crawl complete: %d sources, %d items inserted, %d errors",
            len(sources),
            total_inserted,
            errors,
        )
    finally:
        session.close()

    return {
        "status": "completed",
        "sources_crawled": len(results),
        "items_inserted": total_inserted,
        "errors": errors,
        "details": results,
    }
