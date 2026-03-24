from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from aerisun.domain.activity import repository as repo
from aerisun.domain.activity.schemas import (
    ActivityHeatmapRead,
    ActivityHeatmapStatsRead,
    ActivityHeatmapWeekRead,
    CalendarEventRead,
    CalendarRead,
    RecentActivityItemRead,
    RecentActivityRead,
)
from aerisun.domain.waline.service import list_all_waline_records, parse_comment_path


def _avatar_for_name(name: str) -> str:
    return f"https://api.dicebear.com/9.x/notionists/svg?seed={name}"


def _normalize_timestamp(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _trim_excerpt(value: str | None, limit: int = 72) -> str | None:
    if value is None:
        return None

    excerpt = " ".join(value.split()).strip()
    if not excerpt:
        return None
    if len(excerpt) <= limit:
        return excerpt
    return f"{excerpt[: limit - 1]}…"


def list_calendar_events(session: Session, from_date: date, to_date: date) -> CalendarRead:
    events = []
    for published_at, kind, title, slug, href in repo.find_content_events(session):
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

    # Collect all (content_type, slug) pairs for batch title resolution
    title_pairs: list[tuple[str, str]] = []

    comments = list_all_waline_records(status="approved", guestbook_only=False)[:limit]
    comment_pairs = []
    for item in comments:
        pair = parse_comment_path(item.url)
        comment_pairs.append(pair)
        title_pairs.append(pair)

    reactions = repo.find_recent_reactions(session, limit=limit)
    for item in reactions:
        title_pairs.append((item.content_type, item.content_slug))

    # Batch resolve all titles in one pass
    titles = repo.batch_resolve_titles(session, title_pairs)

    for item, (content_type, content_slug) in zip(comments, comment_pairs, strict=True):
        items.append(
            RecentActivityItemRead(
                kind="reply" if item.pid else "comment",
                actor_name=item.nick or "访客",
                actor_avatar=_avatar_for_name(item.nick or "访客"),
                target_title=titles.get((content_type, content_slug), content_slug),
                excerpt=_trim_excerpt(item.comment),
                created_at=_normalize_timestamp(item.created_at),
                href=item.url,
            )
        )

    guestbook = list_all_waline_records(status="approved", guestbook_only=True)[:limit]
    for item in guestbook:
        items.append(
            RecentActivityItemRead(
                kind="guestbook",
                actor_name=item.nick or "访客",
                actor_avatar=_avatar_for_name(item.nick or "访客"),
                target_title="留言板",
                excerpt=_trim_excerpt(item.comment),
                created_at=_normalize_timestamp(item.created_at),
                href="/guestbook",
            )
        )

    for item in reactions:
        actor_name = item.client_token or "匿名访客"
        items.append(
            RecentActivityItemRead(
                kind="like",
                actor_name=actor_name,
                actor_avatar=_avatar_for_name(actor_name),
                target_title=titles.get((item.content_type, item.content_slug), item.content_slug),
                excerpt="留下了一个赞" if item.reaction_type == "like" else item.reaction_type,
                created_at=_normalize_timestamp(item.created_at),
                href=f"/{item.content_type}/{item.content_slug}",
            )
        )

    items.sort(key=lambda item: item.created_at, reverse=True)
    return RecentActivityRead(items=items[:limit])


# Simple TTL cache for heatmap data
_heatmap_cache: dict[str, tuple[float, ActivityHeatmapRead]] = {}
_HEATMAP_TTL = 300  # 5 minutes


def build_activity_heatmap(session: Session, weeks: int = 52, tz_name: str | None = None) -> ActivityHeatmapRead:
    weeks = max(1, min(weeks, 104))
    try:
        tz = ZoneInfo(tz_name) if tz_name else UTC
    except (KeyError, ValueError):
        tz = UTC

    cache_key = f"heatmap_{weeks}_{tz_name or 'UTC'}"
    now = time.monotonic()
    if cache_key in _heatmap_cache:
        cached_at, cached_result = _heatmap_cache[cache_key]
        if now - cached_at < _HEATMAP_TTL:
            return cached_result

    today = datetime.now(tz).date()
    start = today - timedelta(days=today.weekday() + (weeks - 1) * 7)

    # Use SQL GROUP BY for content counts
    daily_counts: defaultdict[date, int] = defaultdict(int)
    daily_counts.update(repo.count_daily_content(session))

    # Waline comments and guestbook (separate SQLite DB, can't use ORM aggregation)
    for item in list_all_waline_records(status="approved", guestbook_only=False):
        dt = _normalize_timestamp(item.created_at).astimezone(tz)
        daily_counts[dt.date()] += 1

    for item in list_all_waline_records(status="approved", guestbook_only=True):
        dt = _normalize_timestamp(item.created_at).astimezone(tz)
        daily_counts[dt.date()] += 1

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
    result = ActivityHeatmapRead(
        stats=ActivityHeatmapStatsRead(
            total_contributions=total_contributions,
            peak_week=peak_week,
            average_per_week=average_per_week,
        ),
        weeks=week_items,
    )

    _heatmap_cache[cache_key] = (now, result)
    return result
