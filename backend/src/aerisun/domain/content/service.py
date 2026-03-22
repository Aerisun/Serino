from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import (
    DiaryEntry,
    ExcerptEntry,
    PostEntry,
    ThoughtEntry,
)
from aerisun.domain.content.schemas import ContentCollectionRead, ContentEntryRead
from aerisun.domain.engagement.models import Reaction
from aerisun.domain.waline.service import build_comment_path, count_records_by_urls

ContentModel = TypeVar(
    "ContentModel", PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry
)


def _estimate_read_time(value: str) -> str:
    return f"{max(1, round(len(value) / 180))} 分钟"


def _format_display_date(value: datetime | None) -> str | None:
    if value is None:
        return None

    reference = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return f"{reference.year} 年 {reference.month} 月 {reference.day} 日"


def _format_relative_date(value: datetime | None) -> str | None:
    if value is None:
        return None

    reference = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    delta = now - reference
    total_seconds = max(0, int(delta.total_seconds()))
    total_days = delta.days

    if total_seconds < 3600:
        minutes = max(1, total_seconds // 60) if total_seconds else 0
        return f"{minutes} 分钟前"

    if total_days <= 0:
        return f"{max(1, total_seconds // 3600)} 小时前"
    if total_days == 1:
        return "昨天"
    if total_days < 7:
        return f"{total_days} 天前"
    if total_days < 30:
        return f"{max(1, total_days // 7)} 周前"
    if total_days < 365:
        return f"{max(1, total_days // 30)} 个月前"
    return f"{max(1, total_days // 365)} 年前"


def _public_query(model: type[ContentModel]) -> Select[tuple[ContentModel]]:
    return (
        select(model)
        .where(model.status == "published", model.visibility == "public")
        .order_by(desc(model.published_at), desc(model.created_at))
    )


def _comment_counts_by_slug(
    session: Session, content_type: str, slugs: list[str]
) -> dict[str, int]:
    if not slugs:
        return {}

    paths = [build_comment_path(content_type, slug) for slug in slugs]
    counts_by_path = count_records_by_urls(urls=paths, status="approved")
    return {slug: counts_by_path.get(build_comment_path(content_type, slug), 0) for slug in slugs}


def _like_counts_by_slug(
    session: Session, content_type: str, slugs: list[str]
) -> dict[str, int]:
    if not slugs:
        return {}

    rows = session.execute(
        select(Reaction.content_slug, func.count(Reaction.id))
        .where(
            Reaction.content_type == content_type,
            Reaction.content_slug.in_(slugs),
            Reaction.reaction_type == "like",
        )
        .group_by(Reaction.content_slug)
    ).all()
    return {slug: count for slug, count in rows}


def _to_entry(
    item: ContentModel,
    content_type: str,
    comment_counts: dict[str, int],
    like_counts: dict[str, int],
) -> ContentEntryRead:
    published_reference = item.published_at or item.created_at

    # Read type-specific fields directly from the model
    category = getattr(item, "category", None)
    mood = getattr(item, "mood", None)
    weather = getattr(item, "weather", None)
    poem = getattr(item, "poem", None)
    author_name = getattr(item, "author_name", None)
    source = getattr(item, "source", None)
    view_count = getattr(item, "view_count", 0) or 0

    return ContentEntryRead(
        slug=item.slug,
        title=item.title,
        summary=item.summary,
        body=item.body,
        tags=item.tags,
        status=item.status,
        visibility=item.visibility,
        published_at=item.published_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        category=category,
        read_time=_estimate_read_time(item.body),
        display_date=_format_display_date(published_reference),
        relative_date=_format_relative_date(published_reference),
        view_count=view_count,
        comment_count=comment_counts.get(item.slug, 0),
        like_count=like_counts.get(item.slug, 0),
        repost_count=0,
        mood=mood,
        weather=weather,
        poem=poem,
        author=author_name,
        source=source,
    )


def _list_entries(
    session: Session,
    model: type[ContentModel],
    content_type: str,
    limit: int,
    offset: int = 0,
) -> ContentCollectionRead:
    base_query = _public_query(model)
    total = session.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    rows = session.scalars(base_query.offset(offset).limit(limit)).all()
    slugs = [row.slug for row in rows]
    comment_counts = _comment_counts_by_slug(session, content_type, slugs)
    like_counts = _like_counts_by_slug(session, content_type, slugs)
    return ContentCollectionRead(
        items=[_to_entry(row, content_type, comment_counts, like_counts) for row in rows],
        total=total,
        has_more=offset + limit < total,
    )


def _get_by_slug(session: Session, model: type[ContentModel], content_type: str, slug: str) -> ContentEntryRead:
    item = session.scalars(_public_query(model).where(model.slug == slug).limit(1)).first()
    if item is None:
        raise LookupError(f"{model.__name__} with slug '{slug}' was not found")
    comment_counts = _comment_counts_by_slug(session, content_type, [item.slug])
    like_counts = _like_counts_by_slug(session, content_type, [item.slug])
    return _to_entry(item, content_type, comment_counts, like_counts)


def list_public_posts(
    session: Session, limit: int = 20, offset: int = 0
) -> ContentCollectionRead:
    return _list_entries(session, PostEntry, "posts", limit, offset)


def get_public_post(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, PostEntry, "posts", slug)


def list_public_diary_entries(
    session: Session, limit: int = 20, offset: int = 0
) -> ContentCollectionRead:
    return _list_entries(session, DiaryEntry, "diary", limit, offset)


def get_public_diary_entry(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, DiaryEntry, "diary", slug)


def list_public_thoughts(
    session: Session, limit: int = 40, offset: int = 0
) -> ContentCollectionRead:
    return _list_entries(session, ThoughtEntry, "thoughts", limit, offset)


def list_public_excerpts(
    session: Session, limit: int = 40, offset: int = 0
) -> ContentCollectionRead:
    return _list_entries(session, ExcerptEntry, "excerpts", limit, offset)
