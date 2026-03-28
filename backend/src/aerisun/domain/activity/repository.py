from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Reaction

CONTENT_MODELS: dict[str, type] = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}


def _normalize_timestamp(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def find_content_events(session: Session) -> list[tuple[datetime, str, str, str, str]]:
    """Query content models for (published_at, kind, title, slug, href) tuples."""
    items: list[tuple[datetime, str, str, str, str]] = []
    mappings = [
        (PostEntry, "post", "/posts/{slug}"),
        (DiaryEntry, "diary", "/diary/{slug}"),
        (ExcerptEntry, "excerpt", "/excerpts"),
    ]
    for model, kind, href_template in mappings:
        rows = session.scalars(
            select(model)
            .where(
                model.status == "published",
                model.visibility == "public",
                model.published_at.is_not(None),
            )
            .order_by(desc(model.published_at))
        ).all()
        for row in rows:
            assert row.published_at is not None
            href = href_template.format(slug=row.slug)
            items.append((row.published_at, kind, row.title, row.slug, href))
    return items


def batch_resolve_titles(session: Session, pairs: list[tuple[str, str]]) -> dict[tuple[str, str], str]:
    """Batch resolve {(content_type, slug): title}."""
    if not pairs:
        return {}

    by_type: dict[str, list[str]] = defaultdict(list)
    for ct, slug in pairs:
        by_type[ct].append(slug)

    result: dict[tuple[str, str], str] = {}
    for ct, slugs in by_type.items():
        model = CONTENT_MODELS.get(ct)
        if model is None:
            for slug in slugs:
                result[(ct, slug)] = slug
            continue
        rows = session.execute(select(model.slug, model.title).where(model.slug.in_(slugs))).all()
        found = {slug: title for slug, title in rows}
        for slug in slugs:
            result[(ct, slug)] = found.get(slug, slug)
    return result


def count_daily_content(session: Session, *, tz: ZoneInfo) -> dict[date, int]:
    """Aggregate public content publish counts by day in the requested timezone."""
    daily: dict[date, int] = defaultdict(int)
    for model in [PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry]:
        published_at_values = session.scalars(
            select(model.published_at).where(
                model.status == "published",
                model.visibility == "public",
                model.published_at.is_not(None),
            )
        ).all()
        for published_at in published_at_values:
            if published_at is None:
                continue
            daily[_normalize_timestamp(published_at).astimezone(tz).date()] += 1
    return daily


def count_daily_likes(session: Session, *, tz: ZoneInfo) -> dict[date, int]:
    """Aggregate like reactions by day in the requested timezone."""
    daily: dict[date, int] = defaultdict(int)
    created_at_values = session.scalars(
        select(Reaction.created_at).where(Reaction.reaction_type == "like"),
    ).all()
    for created_at in created_at_values:
        daily[_normalize_timestamp(created_at).astimezone(tz).date()] += 1
    return daily


def find_recent_reactions(session: Session, *, limit: int) -> list[Reaction]:
    """Fetch recent reactions ordered by created_at desc."""
    return list(session.scalars(select(Reaction).order_by(desc(Reaction.created_at)).limit(limit)).all())
