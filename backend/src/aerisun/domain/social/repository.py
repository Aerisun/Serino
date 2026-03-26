from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from aerisun.domain.social.models import Friend, FriendFeedItem, FriendFeedSource


def find_active_friends(session: Session, *, limit: int = 100) -> list[Friend]:
    """Query active friends in random order."""
    return list(
        session.scalars(
            select(Friend)
            .where(Friend.status == "active")
            .order_by(func.random())
            .limit(limit)
        ).all()
    )


def find_recent_feed_items(session: Session, *, limit: int = 20) -> list[tuple[FriendFeedItem, Friend]]:
    """Query recent feed items joined with their friend. Returns (item, friend) tuples."""
    return list(
        session.execute(
            select(FriendFeedItem, Friend)
            .join(FriendFeedSource, FriendFeedItem.source_id == FriendFeedSource.id)
            .join(Friend, FriendFeedSource.friend_id == Friend.id)
            .where(Friend.status == "active", FriendFeedSource.is_enabled.is_(True))
            .order_by(desc(FriendFeedItem.published_at), desc(FriendFeedItem.created_at))
            .limit(limit)
        ).all()
    )
