from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.core.time import shanghai_now
from aerisun.domain.engagement.models import Reaction
from aerisun.domain.ops.models import TrafficDailySnapshot, VisitRecord
from aerisun.domain.social.models import Friend, FriendFeedItem, FriendFeedSource


def seed_social_data(
    session: Session,
    *,
    default_friends: list[dict],
    default_friend_feed_sources: list[dict],
    default_friend_feed_items: list[dict],
) -> None:
    friends_by_name = {friend.name: friend for friend in session.scalars(select(Friend)).all()}

    for item in default_friends:
        friend = friends_by_name.get(item["name"])
        if friend is None:
            friend = Friend(**item)
            session.add(friend)
            session.flush()
            friends_by_name[friend.name] = friend
            continue

        if not friend.description:
            friend.description = item["description"]
        if not friend.avatar_url:
            friend.avatar_url = item["avatar_url"]
        if not friend.url:
            friend.url = item["url"]
        if friend.status in {"", "pending"}:
            friend.status = item["status"]
        if friend.order_index == 0:
            friend.order_index = item["order_index"]

    sources_by_name = {
        friend.name: source
        for source, friend in session.execute(
            select(FriendFeedSource, Friend).join(Friend, FriendFeedSource.friend_id == Friend.id)
        ).all()
    }
    for item in default_friend_feed_sources:
        source = sources_by_name.get(item["friend_name"])
        if source is None:
            source = FriendFeedSource(
                friend_id=friends_by_name[item["friend_name"]].id,
                feed_url=item["feed_url"],
                last_fetched_at=item["last_fetched_at"],
                is_enabled=item["is_enabled"],
            )
            session.add(source)
            session.flush()
            sources_by_name[item["friend_name"]] = source
            continue

        if not source.feed_url:
            source.feed_url = item["feed_url"]
        if source.last_fetched_at is None:
            source.last_fetched_at = item["last_fetched_at"]

    existing_feed_urls = set(session.scalars(select(FriendFeedItem.url)).all())
    missing_feed_items = [item for item in default_friend_feed_items if item["url"] not in existing_feed_urls]
    if missing_feed_items:
        session.add_all(
            [
                FriendFeedItem(
                    source_id=sources_by_name[item["friend_name"]].id,
                    title=item["title"],
                    url=item["url"],
                    summary=item["summary"],
                    published_at=item["published_at"],
                    raw_payload=item["raw_payload"],
                )
                for item in missing_feed_items
            ]
        )


def seed_engagement_data(session: Session, *, default_reactions: list[dict]) -> None:
    existing_reactions = {
        (item.content_type, item.content_slug, item.reaction_type, item.client_token)
        for item in session.scalars(select(Reaction)).all()
    }
    missing_reactions = [
        item
        for item in default_reactions
        if (
            item["content_type"],
            item["content_slug"],
            item["reaction_type"],
            item["client_token"],
        )
        not in existing_reactions
    ]
    if missing_reactions:
        session.add_all([Reaction(**item) for item in missing_reactions])


def seed_traffic_snapshot_data(session: Session, *, default_traffic_snapshots: list[dict]) -> None:
    existing = session.scalar(select(func.count(TrafficDailySnapshot.id)))
    if existing and int(existing) > 0:
        return
    session.add_all([TrafficDailySnapshot(**item) for item in default_traffic_snapshots])


def seed_visit_record_data(session: Session) -> None:
    existing = session.scalar(select(func.count(VisitRecord.id)))
    if existing and int(existing) > 0:
        return

    now = shanghai_now()
    sample = []
    ip_pool = [
        "203.0.113.10",
        "203.0.113.11",
        "203.0.113.12",
        "198.51.100.7",
        "198.51.100.8",
    ]
    paths = [
        "/",
        "/posts/from-zero-design-system",
        "/posts/crafting-an-editorial-homepage",
        "/posts/liquid-glass-css-notes",
        "/diary/spring-equinox-and-warm-light",
        "/thoughts/small-routines-build-better-systems",
        "/resume",
        "/friends",
        "/guestbook",
    ]

    for day_offset in range(14):
        day = now - timedelta(days=13 - day_offset)
        visits_today = 3 + (day_offset % 6)
        for idx in range(visits_today):
            path = paths[(day_offset * 3 + idx) % len(paths)]
            ip = ip_pool[(day_offset + idx) % len(ip_pool)]
            sample.append(
                VisitRecord(
                    visited_at=day.replace(hour=(9 + idx) % 24, minute=(idx * 7) % 60, second=0, microsecond=0),
                    path=path,
                    ip_address=ip,
                    user_agent="Mozilla/5.0 (Seed) AppleWebKit/537.36",
                    referer="https://example.com" if idx % 3 == 0 else None,
                    status_code=200,
                    duration_ms=60 + (idx * 23) % 240,
                    is_bot=False,
                )
            )

    sample.append(
        VisitRecord(
            visited_at=now - timedelta(hours=6),
            path="/robots.txt",
            ip_address="192.0.2.66",
            user_agent="Googlebot/2.1 (+http://www.google.com/bot.html)",
            referer=None,
            status_code=200,
            duration_ms=20,
            is_bot=True,
        )
    )

    session.add_all(sample)
