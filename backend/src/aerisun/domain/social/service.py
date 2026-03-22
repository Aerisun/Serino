from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from aerisun.domain.social.models import Friend, FriendFeedItem, FriendFeedSource
from aerisun.domain.social.schemas import (
    FriendCollectionRead,
    FriendFeedCollectionRead,
    FriendFeedItemRead,
    FriendRead,
)


def _avatar_for_name(name: str) -> str:
    return f"https://api.dicebear.com/9.x/notionists/svg?seed={name}"


def list_public_friends(session: Session, limit: int = 100) -> FriendCollectionRead:
    items = session.scalars(
        select(Friend)
        .where(Friend.status == "active")
        .order_by(Friend.order_index.asc(), Friend.created_at.asc())
        .limit(limit)
    ).all()
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
    rows = session.execute(
        select(FriendFeedItem, Friend)
        .join(FriendFeedSource, FriendFeedItem.source_id == FriendFeedSource.id)
        .join(Friend, FriendFeedSource.friend_id == Friend.id)
        .where(Friend.status == "active", FriendFeedSource.is_enabled.is_(True))
        .order_by(desc(FriendFeedItem.published_at), desc(FriendFeedItem.created_at))
        .limit(limit)
    ).all()
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
