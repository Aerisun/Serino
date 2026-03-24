from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.social import repository as repo
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
