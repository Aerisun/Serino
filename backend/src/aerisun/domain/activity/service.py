from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Comment, GuestbookEntry, Reaction
from aerisun.domain.activity.schemas import (
    ActivityHeatmapRead,
    ActivityHeatmapStatsRead,
    ActivityHeatmapWeekRead,
    CalendarEventRead,
    CalendarRead,
    RecentActivityItemRead,
    RecentActivityRead,
)


CONTENT_MODELS = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}


def _avatar_for_name(name: str) -> str:
    return f"https://api.dicebear.com/9.x/notionists/svg?seed={name}"


def _trim_excerpt(value: str | None, limit: int = 72) -> str | None:
    if value is None:
        return None

    excerpt = " ".join(value.split()).strip()
    if not excerpt:
        return None
    if len(excerpt) <= limit:
        return excerpt
    return f"{excerpt[: limit - 1]}…"


def _content_events(session: Session) -> list[tuple[datetime, str, str, str, str]]:
    items: list[tuple[datetime, str, str, str, str]] = []
    mappings = [
        (PostEntry, "post", "/posts/{slug}"),
        (DiaryEntry, "diary", "/diary/{slug}"),
        (ExcerptEntry, "excerpt", "/excerpts"),
    ]
    for model, kind, href_template in mappings:
        rows = session.scalars(
            select(model)
            .where(model.status == "published", model.visibility == "public", model.published_at.is_not(None))
            .order_by(desc(model.published_at))
        ).all()
        for row in rows:
            assert row.published_at is not None
            href = href_template.format(slug=row.slug)
            items.append((row.published_at, kind, row.title, row.slug, href))
    return items


def _resolve_content_title(session: Session, content_type: str, content_slug: str) -> str:
    model = CONTENT_MODELS.get(content_type)
    if model is None:
        return content_slug

    title = session.scalar(select(model.title).where(model.slug == content_slug))
    return title or content_slug


def list_calendar_events(session: Session, from_date: date, to_date: date) -> CalendarRead:
    events = []
    for published_at, kind, title, slug, href in _content_events(session):
        current = published_at.date()
        if from_date <= current <= to_date:
            events.append(
                CalendarEventRead(
                    date=current.isoformat(),
                    type=kind,
                    title=title,
                    slug=slug,
                    href=href,
                )
            )
    events.sort(key=lambda item: (item.date, item.type, item.title), reverse=True)
    return CalendarRead(
        range_start=from_date.isoformat(),
        range_end=to_date.isoformat(),
        events=events,
    )

def list_recent_activity(session: Session, limit: int = 8) -> RecentActivityRead:
    items: list[RecentActivityItemRead] = []

    comments = session.scalars(
        select(Comment)
        .where(Comment.status == "approved")
        .order_by(desc(Comment.created_at))
        .limit(limit)
    ).all()
    for item in comments:
        items.append(
            RecentActivityItemRead(
                kind="reply" if item.parent_id else "comment",
                actor_name=item.author_name,
                actor_avatar=_avatar_for_name(item.author_name),
                target_title=_resolve_content_title(session, item.content_type, item.content_slug),
                excerpt=_trim_excerpt(item.body),
                created_at=item.created_at,
                href=f"/{item.content_type}/{item.content_slug}",
            )
        )

    guestbook = session.scalars(
        select(GuestbookEntry)
        .where(GuestbookEntry.status == "approved")
        .order_by(desc(GuestbookEntry.created_at))
        .limit(limit)
    ).all()
    for item in guestbook:
        items.append(
            RecentActivityItemRead(
                kind="guestbook",
                actor_name=item.name,
                actor_avatar=_avatar_for_name(item.name),
                target_title="留言板",
                excerpt=_trim_excerpt(item.body),
                created_at=item.created_at,
                href="/guestbook",
            )
        )

    reactions = session.scalars(
        select(Reaction)
        .order_by(desc(Reaction.created_at))
        .limit(limit)
    ).all()
    for item in reactions:
        actor_name = item.client_token or "匿名访客"
        items.append(
            RecentActivityItemRead(
                kind="like",
                actor_name=actor_name,
                actor_avatar=_avatar_for_name(actor_name),
                target_title=_resolve_content_title(session, item.content_type, item.content_slug),
                excerpt="留下了一个赞" if item.reaction_type == "like" else item.reaction_type,
                created_at=item.created_at,
                href=f"/{item.content_type}/{item.content_slug}",
            )
        )

    items.sort(key=lambda item: item.created_at, reverse=True)
    return RecentActivityRead(items=items[:limit])


def build_activity_heatmap(session: Session, weeks: int = 52) -> ActivityHeatmapRead:
    weeks = max(1, min(weeks, 104))
    today = datetime.now(UTC).date()
    start = today - timedelta(days=today.weekday() + (weeks - 1) * 7)

    daily_counts: dict[date, int] = defaultdict(int)
    for published_at, _, _, _, _ in _content_events(session):
        daily_counts[published_at.date()] += 1

    comment_dates = session.scalars(
        select(Comment.created_at).where(Comment.status == "approved")
    ).all()
    for created_at in comment_dates:
        daily_counts[created_at.date()] += 1

    guestbook_dates = session.scalars(
        select(GuestbookEntry.created_at).where(GuestbookEntry.status == "approved")
    ).all()
    for created_at in guestbook_dates:
        daily_counts[created_at.date()] += 1

    week_items: list[ActivityHeatmapWeekRead] = []
    totals: list[int] = []
    for index in range(weeks):
        week_start = start + timedelta(days=index * 7)
        days = [daily_counts[week_start + timedelta(days=offset)] for offset in range(7)]
        total = sum(days)
        totals.append(total)
        week_items.append(
            ActivityHeatmapWeekRead(
                week_start=week_start.isoformat(),
                total=total,
                days=days,
                month_label=week_start.strftime("%b"),
                label=f"{week_start.strftime('%b')} {week_start.day}",
            )
        )

    total_contributions = sum(totals)
    peak_week = max(totals, default=0)
    average_per_week = round(total_contributions / weeks) if weeks else 0
    return ActivityHeatmapRead(
        stats=ActivityHeatmapStatsRead(
            total_contributions=total_contributions,
            peak_week=peak_week,
            average_per_week=average_per_week,
        ),
        weeks=week_items,
    )
