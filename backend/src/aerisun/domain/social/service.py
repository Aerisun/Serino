from __future__ import annotations

import logging

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.social import repository as repo
from aerisun.domain.social.schemas import (
    FriendCollectionRead,
    FriendFeedCollectionRead,
    FriendFeedItemRead,
    FriendFeedSourceAdminRead,
    FriendRead,
)

logger = logging.getLogger(__name__)


def _crawl_source_best_effort(session: Session, source_id: str) -> dict | None:
    """Crawl a feed source without failing the surrounding admin mutation."""
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.crawler import crawl_single_source
    from aerisun.domain.social.models import Friend, FriendFeedSource

    source = session.get(FriendFeedSource, source_id)
    if source is None or not source.is_enabled:
        return None

    friend = session.get(Friend, source.friend_id)
    if friend is None or friend.status != "active":
        return None

    try:
        result = crawl_single_source(session, source, friend, get_settings())
        session.commit()
        return result
    except Exception:
        logger.exception("Immediate crawl failed for feed source %s", source_id)
        session.rollback()

        source = session.get(FriendFeedSource, source_id)
        if source is not None:
            source.last_error = "unexpected crawl failure"
            session.commit()
        return None


def list_public_friends(session: Session, limit: int = 100) -> FriendCollectionRead:
    items = repo.find_active_friends(session, limit=limit)
    return FriendCollectionRead(
        items=[
            FriendRead(
                name=item.name,
                description=item.description,
                avatar=item.avatar_url or "",
                url=item.url,
                status=item.status,
            )
            for item in items
        ]
    )


def list_public_friend_feed(session: Session, limit: int = 20) -> FriendFeedCollectionRead:
    rows = repo.find_recent_feed_items(session, limit=limit)
    return FriendFeedCollectionRead(
        items=[
            FriendFeedItemRead(
                title=item.title,
                summary=item.summary,
                url=item.url,
                blogName=friend.name,
                avatar=friend.avatar_url or "",
                publishedAt=item.published_at or item.created_at,
            )
            for item, friend in rows
        ]
    )


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------


def trigger_single_crawl(session: Session, feed_id: str):
    """Trigger crawl for a single feed source. Raises ResourceNotFound."""
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.crawler import crawl_single_source
    from aerisun.domain.social.models import Friend, FriendFeedSource

    source = session.get(FriendFeedSource, feed_id)
    if source is None:
        raise ResourceNotFound("Feed source not found")
    friend = session.get(Friend, source.friend_id)
    if friend is None:
        raise ResourceNotFound("Friend not found")
    result = crawl_single_source(session, source, friend, get_settings())
    session.commit()
    return result


def check_friend_now(session: Session, friend_id: str) -> dict[str, object]:
    """Immediately check one friend website and its enabled RSS sources."""
    from aerisun.core.base import utcnow
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.crawler import crawl_single_source
    from aerisun.domain.social.models import Friend, FriendFeedSource
    from aerisun.domain.social.monitor import check_single_friend_site

    friend = session.get(Friend, friend_id)
    if friend is None:
        raise ResourceNotFound("Friend not found")

    site_result = check_single_friend_site(session, friend_id, get_settings())
    session.refresh(friend)

    rss_results: list[dict[str, object]] = []
    if friend.status != "archived":
        sources = session.query(FriendFeedSource).filter(FriendFeedSource.friend_id == friend_id).all()
        for source in sources:
            if not source.is_enabled:
                continue
            if friend.status != "active":
                source.last_fetched_at = utcnow()
                source.last_error = "website unreachable"
                session.commit()
                rss_results.append(
                    {
                        "source_id": source.id,
                        "friend_name": friend.name,
                        "status": "error",
                        "inserted": 0,
                        "feed_url_updated": False,
                        "error": source.last_error,
                    }
                )
                continue

            result = crawl_single_source(session, source, friend, get_settings())
            session.commit()
            rss_results.append(result)

    session.refresh(friend)
    return {
        "friend_id": friend.id,
        "website_status": friend.status,
        "rss_status": friend.rss_status,
        "site_result": site_result,
        "rss_results": rss_results,
    }


def list_friend_feeds_admin(session: Session, friend_id: str) -> list[FriendFeedSourceAdminRead]:
    """List feed sources for a friend. Raises ResourceNotFound."""
    from aerisun.domain.social.models import Friend, FriendFeedSource

    friend = session.get(Friend, friend_id)
    if friend is None:
        raise ResourceNotFound("Friend not found")
    sources = session.query(FriendFeedSource).filter(FriendFeedSource.friend_id == friend_id).all()
    return [FriendFeedSourceAdminRead.model_validate(s) for s in sources]


def create_friend_feed_admin(session: Session, friend_id: str, payload: BaseModel) -> FriendFeedSourceAdminRead:
    """Create a feed source for a friend. Raises ResourceNotFound."""
    from aerisun.domain.automation.events import emit_friend_feed_source_created
    from aerisun.domain.social.models import Friend, FriendFeedSource

    friend = session.get(Friend, friend_id)
    if friend is None:
        raise ResourceNotFound("Friend not found")
    data = payload.model_dump()
    data["friend_id"] = friend_id
    obj = FriendFeedSource(**data)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    emit_friend_feed_source_created(
        session,
        source_id=obj.id,
        friend_id=friend_id,
        feed_url=obj.feed_url,
    )
    _crawl_source_best_effort(session, obj.id)
    session.refresh(obj)
    return FriendFeedSourceAdminRead.model_validate(obj)


def update_friend_feed_admin(session: Session, feed_id: str, payload: BaseModel) -> FriendFeedSourceAdminRead:
    """Update a feed source. Raises ResourceNotFound."""
    from aerisun.domain.automation.events import emit_friend_feed_source_updated
    from aerisun.domain.social.models import FriendFeedItem, FriendFeedSource

    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise ResourceNotFound("Feed source not found")

    updates = payload.model_dump(exclude_unset=True)
    changed_fields = sorted(updates.keys())
    previous_feed_url = obj.feed_url
    previous_enabled = obj.is_enabled

    for key, value in updates.items():
        setattr(obj, key, value)

    feed_url_changed = "feed_url" in updates and updates["feed_url"] != previous_feed_url
    enabled_after_update = obj.is_enabled

    if feed_url_changed:
        # A different source should not inherit stale cache state or items from the old feed.
        obj.etag = None
        obj.last_fetched_at = None
        obj.last_error = None
        session.execute(delete(FriendFeedItem).where(FriendFeedItem.source_id == obj.id))

    session.commit()
    emit_friend_feed_source_updated(
        session,
        source_id=obj.id,
        friend_id=obj.friend_id,
        feed_url=obj.feed_url,
        changed_fields=changed_fields,
    )
    if enabled_after_update and (feed_url_changed or not previous_enabled):
        _crawl_source_best_effort(session, obj.id)
    session.refresh(obj)
    return FriendFeedSourceAdminRead.model_validate(obj)


def delete_friend_feed_admin(session: Session, feed_id: str) -> None:
    """Delete a feed source. Raises ResourceNotFound."""
    from aerisun.domain.automation.events import emit_friend_feed_source_deleted
    from aerisun.domain.social.models import FriendFeedSource

    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise ResourceNotFound("Feed source not found")
    snapshot = {"source_id": obj.id, "friend_id": obj.friend_id, "feed_url": obj.feed_url}
    session.delete(obj)
    session.commit()
    emit_friend_feed_source_deleted(session, **snapshot)
