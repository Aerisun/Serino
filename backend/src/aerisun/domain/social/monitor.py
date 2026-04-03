from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import or_, select

from aerisun.core.base import utcnow
from aerisun.core.db import get_session_factory
from aerisun.core.settings import Settings, get_settings
from aerisun.domain.site_config.models import PageCopy
from aerisun.domain.social.crawler import _build_headers, crawl_single_source
from aerisun.domain.social.models import Friend, FriendFeedSource

logger = logging.getLogger(__name__)

FRIENDS_PAGE_KEY = "friends"


def _parse_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _parse_positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def load_friend_monitor_config(session, settings: Settings | None = None) -> dict[str, int | bool]:
    if settings is None:
        settings = get_settings()

    default_interval_minutes = max(60, settings.feed_crawl_interval_hours * 60)
    defaults: dict[str, int | bool] = {
        "websiteHealthCheckEnabled": True,
        "websiteHealthCheckIntervalMinutes": default_interval_minutes,
        "rssHealthCheckEnabled": True,
        "rssHealthCheckIntervalMinutes": default_interval_minutes,
    }

    page_copy = session.scalar(select(PageCopy).where(PageCopy.page_key == FRIENDS_PAGE_KEY))
    extras = dict(page_copy.extras or {}) if page_copy else {}

    return {
        "websiteHealthCheckEnabled": _parse_bool(
            extras.get("websiteHealthCheckEnabled"),
            defaults["websiteHealthCheckEnabled"],  # type: ignore[arg-type]
        ),
        "websiteHealthCheckIntervalMinutes": _parse_positive_int(
            extras.get("websiteHealthCheckIntervalMinutes"),
            defaults["websiteHealthCheckIntervalMinutes"],  # type: ignore[arg-type]
        ),
        "rssHealthCheckEnabled": _parse_bool(
            extras.get("rssHealthCheckEnabled"),
            defaults["rssHealthCheckEnabled"],  # type: ignore[arg-type]
        ),
        "rssHealthCheckIntervalMinutes": _parse_positive_int(
            extras.get("rssHealthCheckIntervalMinutes"),
            defaults["rssHealthCheckIntervalMinutes"],  # type: ignore[arg-type]
        ),
    }


def _build_timeout(settings: Settings) -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.feed_crawl_timeout_connect,
        read=settings.feed_crawl_timeout_read,
        write=10.0,
        pool=10.0,
    )


def _probe_friend_site(friend: Friend, client: httpx.Client) -> dict[str, Any]:
    previous_status = friend.status
    normalized_url = (friend.url or "").strip()
    if normalized_url != friend.url:
        friend.url = normalized_url

    result: dict[str, Any] = {
        "friend_id": friend.id,
        "friend_name": friend.name,
        "status": friend.status,
        "previous_status": previous_status,
    }

    if friend.status == "archived":
        result["status"] = "archived"
        return result

    if not normalized_url:
        friend.status = "lost"
        friend.last_checked_at = utcnow()
        friend.last_error = "website url is blank"
        result["status"] = "lost"
        result["error"] = friend.last_error
        return result

    try:
        response = client.get(normalized_url)
        friend.last_checked_at = utcnow()
        if response.status_code < 500:
            friend.status = "active"
            friend.last_error = None
            result["status"] = "active"
        else:
            friend.status = "lost"
            friend.last_error = f"HTTP {response.status_code}"
            result["status"] = "lost"
            result["error"] = friend.last_error
    except httpx.HTTPError as exc:
        friend.status = "lost"
        friend.last_checked_at = utcnow()
        friend.last_error = str(exc)
        result["status"] = "lost"
        result["error"] = friend.last_error

    return result


def check_single_friend_site(session, friend_id: str, settings: Settings | None = None) -> dict[str, Any]:
    if settings is None:
        settings = get_settings()

    friend = session.get(Friend, friend_id)
    if friend is None:
        return {"status": "missing", "friend_id": friend_id}

    with httpx.Client(
        headers=_build_headers(settings),
        timeout=_build_timeout(settings),
        follow_redirects=True,
    ) as client:
        result = _probe_friend_site(friend, client)

    session.commit()
    return result


def run_due_friend_site_checks(settings: Settings | None = None) -> dict[str, Any]:
    from aerisun.domain.automation.events import emit_friend_site_checked

    if settings is None:
        settings = get_settings()

    factory = get_session_factory()
    session = factory()
    try:
        config = load_friend_monitor_config(session, settings)
        if not config["websiteHealthCheckEnabled"]:
            return {"status": "skipped", "checked": 0, "details": []}

        threshold = utcnow() - timedelta(minutes=int(config["websiteHealthCheckIntervalMinutes"]))
        friends = list(
            session.scalars(
                select(Friend).where(
                    Friend.status != "archived",
                    or_(Friend.last_checked_at.is_(None), Friend.last_checked_at <= threshold),
                )
            ).all()
        )

        if not friends:
            return {"status": "idle", "checked": 0, "details": []}

        details: list[dict[str, Any]] = []
        with httpx.Client(
            headers=_build_headers(settings),
            timeout=_build_timeout(settings),
            follow_redirects=True,
        ) as client:
            for friend in friends:
                details.append(_probe_friend_site(friend, client))
            session.commit()
            for detail in details:
                emit_friend_site_checked(
                    session,
                    friend_id=str(detail.get("friend_id") or ""),
                    friend_name=str(detail.get("friend_name") or ""),
                    previous_status=str(detail.get("previous_status") or ""),
                    status=str(detail.get("status") or ""),
                    error=str(detail.get("error") or "") or None,
                )

        return {"status": "completed", "checked": len(details), "details": details}
    finally:
        session.close()


def run_due_rss_health_checks(settings: Settings | None = None) -> dict[str, Any]:
    from aerisun.domain.automation.events import emit_friend_feed_checked

    if settings is None:
        settings = get_settings()

    factory = get_session_factory()
    session = factory()
    try:
        config = load_friend_monitor_config(session, settings)
        if not config["rssHealthCheckEnabled"]:
            return {"status": "skipped", "checked": 0, "details": []}

        threshold = utcnow() - timedelta(minutes=int(config["rssHealthCheckIntervalMinutes"]))
        sources = list(
            session.execute(
                select(FriendFeedSource, Friend)
                .join(Friend, FriendFeedSource.friend_id == Friend.id)
                .where(
                    FriendFeedSource.is_enabled.is_(True),
                    Friend.status != "archived",
                    or_(
                        FriendFeedSource.last_fetched_at.is_(None),
                        FriendFeedSource.last_fetched_at <= threshold,
                    ),
                )
            ).all()
        )

        if not sources:
            return {"status": "idle", "checked": 0, "details": []}

        details: list[dict[str, Any]] = []
        for source, friend in sources:
            if friend.status == "lost":
                source.last_fetched_at = utcnow()
                source.last_error = "website unreachable"
                session.commit()
                details.append(
                    {
                        "source_id": source.id,
                        "friend_id": friend.id,
                        "friend_name": friend.name,
                        "status": "error",
                        "error": source.last_error,
                        "inserted": 0,
                        "feed_url_updated": False,
                    }
                )
                continue

            try:
                details.append(crawl_single_source(session, source, friend, settings))
                session.commit()
            except Exception:
                logger.exception("Error checking RSS for source %s", source.id)
                session.rollback()
                details.append(
                    {
                        "source_id": source.id,
                        "friend_id": friend.id,
                        "friend_name": friend.name,
                        "status": "error",
                        "error": "unexpected exception",
                        "inserted": 0,
                        "feed_url_updated": False,
                    }
                )

        for detail in details:
            emit_friend_feed_checked(
                session,
                source_id=str(detail.get("source_id") or ""),
                friend_id=str(detail.get("friend_id") or ""),
                friend_name=str(detail.get("friend_name") or ""),
                status=str(detail.get("status") or ""),
                inserted=int(detail.get("inserted") or 0),
                feed_url_updated=bool(detail.get("feed_url_updated")),
                error=str(detail.get("error") or "") or None,
            )

        return {"status": "completed", "checked": len(details), "details": details}
    finally:
        session.close()


def dispatch_due_social_checks(settings: Settings | None = None) -> dict[str, Any]:
    if settings is None:
        settings = get_settings()

    site_result = run_due_friend_site_checks(settings)
    rss_result = run_due_rss_health_checks(settings)
    return {
        "status": "completed",
        "site_checks": site_result,
        "rss_checks": rss_result,
    }
