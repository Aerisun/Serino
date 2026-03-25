from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.social import repository as repo
from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.social.schemas import (
    FriendCollectionRead,
    FriendFeedCollectionRead,
    FriendFeedItemRead,
    FriendRead,
)


def _avatar_for_name(name: str) -> str:
    return f"https://api.dicebear.com/9.x/notionists/svg?seed={name}"


def list_public_friends(session: Session, limit: int = 100) -> FriendCollectionRead:
    items = repo.find_active_friends(session, limit=limit)
    return FriendCollectionRead(
        items=[
            FriendRead(
                name=item.name,
                description=item.description,
                avatar=item.avatar_url or _avatar_for_name(item.name),
                url=item.url,
                status=item.status,
                order_index=item.order_index,
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
                avatar=friend.avatar_url or _avatar_for_name(friend.name),
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


def list_friend_feeds_admin(session: Session, friend_id: str):
    """List feed sources for a friend. Raises ResourceNotFound."""
    from aerisun.domain.social.models import Friend, FriendFeedSource

    friend = session.get(Friend, friend_id)
    if friend is None:
        raise ResourceNotFound("Friend not found")
    sources = session.query(FriendFeedSource).filter(FriendFeedSource.friend_id == friend_id).all()
    return sources


def create_friend_feed_admin(session: Session, friend_id: str, data: dict):
    """Create a feed source for a friend. Raises ResourceNotFound."""
    from aerisun.domain.social.models import Friend, FriendFeedSource

    friend = session.get(Friend, friend_id)
    if friend is None:
        raise ResourceNotFound("Friend not found")
    data["friend_id"] = friend_id
    obj = FriendFeedSource(**data)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def update_friend_feed_admin(session: Session, feed_id: str, data: dict):
    """Update a feed source. Raises ResourceNotFound."""
    from aerisun.domain.social.models import FriendFeedSource

    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise ResourceNotFound("Feed source not found")
    for key, value in data.items():
        setattr(obj, key, value)
    session.commit()
    session.refresh(obj)
    return obj


def delete_friend_feed_admin(session: Session, feed_id: str) -> None:
    """Delete a feed source. Raises ResourceNotFound."""
    from aerisun.domain.social.models import FriendFeedSource

    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise ResourceNotFound("Feed source not found")
    session.delete(obj)
    session.commit()
