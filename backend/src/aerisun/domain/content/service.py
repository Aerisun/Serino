from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.core.base import uuid_str
from aerisun.domain.content import repository as repo
from aerisun.domain.content.models import (
    ContentCategory,
    DiaryEntry,
    ExcerptEntry,
    PostEntry,
    ThoughtEntry,
)
from aerisun.domain.content.schemas import ContentCategoryRead, ContentCollectionRead, ContentEntryRead
from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.waline.service import build_comment_path, count_records_by_urls, get_counter_stats_by_urls

ContentModel = TypeVar("ContentModel", PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)

CONTENT_CATEGORY_TYPES = {"posts", "thoughts", "excerpts"}


CONTENT_STATUS_VALUES = {"draft", "published", "archived"}
CONTENT_VISIBILITY_VALUES = {"public", "private"}
MANAGED_MODEL_CONTENT_TYPES = {
    PostEntry: "posts",
    ThoughtEntry: "thoughts",
    ExcerptEntry: "excerpts",
}


def _normalize_content_state_values(
    *,
    status: str | None,
    visibility: str | None,
    fallback_status: str = "draft",
    fallback_visibility: str = "public",
) -> tuple[str, str]:
    normalized_status = status if status in CONTENT_STATUS_VALUES else fallback_status
    normalized_visibility = visibility if visibility in CONTENT_VISIBILITY_VALUES else fallback_visibility
    return normalized_status, normalized_visibility


def resolve_content_state(
    *,
    current_status: str = "draft",
    current_visibility: str = "public",
    target_status: str | None = None,
    target_visibility: str | None = None,
) -> tuple[str, str]:
    current_status, current_visibility = _normalize_content_state_values(
        status=current_status,
        visibility=current_visibility,
    )
    target_status, target_visibility = _normalize_content_state_values(
        status=target_status,
        visibility=target_visibility,
        fallback_status=current_status,
        fallback_visibility=current_visibility,
    )

    if target_status == "draft":
        return "draft", target_visibility

    if target_visibility == "private":
        return "archived", "private"

    if current_visibility == "private" and current_status == "archived" and target_visibility == "public":
        return "draft", "public"

    return target_status, "public"


def resolve_content_bulk_state(status: str) -> tuple[str, str | None]:
    normalized_status, normalized_visibility = resolve_content_state(
        target_status=status,
        target_visibility="private" if status == "archived" else "public",
    )
    return normalized_status, normalized_visibility


def normalize_content_create_state(session: Session, data: dict) -> dict:
    normalized = dict(data)
    _normalize_and_sync_category(session, normalized, content_type=normalized.pop("_content_type", None))
    resolved_status, resolved_visibility = resolve_content_state(
        target_status=normalized.get("status", "draft"),
        target_visibility=normalized.get("visibility", "public"),
    )
    normalized["status"] = resolved_status
    normalized["visibility"] = resolved_visibility
    return normalized


def normalize_content_update_state(session: Session, existing: ContentModel, patch: dict) -> dict:
    normalized = dict(patch)
    _normalize_and_sync_category(
        session,
        normalized,
        content_type=MANAGED_MODEL_CONTENT_TYPES.get(type(existing)),
    )
    resolved_status, resolved_visibility = resolve_content_state(
        current_status=getattr(existing, "status", "draft") or "draft",
        current_visibility=getattr(existing, "visibility", "public") or "public",
        target_status=normalized.get("status"),
        target_visibility=normalized.get("visibility"),
    )
    normalized["status"] = resolved_status
    normalized["visibility"] = resolved_visibility
    return normalized


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


def _engagement_stats_by_slug(content_type: str, slugs: list[str]) -> dict[str, dict[str, int | None]]:
    if not slugs:
        return {}

    paths = [build_comment_path(content_type, slug) for slug in slugs]
    counts_by_path = count_records_by_urls(urls=paths, status="approved")
    counter_stats_by_path = get_counter_stats_by_urls(urls=paths)
    stats_by_slug: dict[str, dict[str, int | None]] = {}
    for slug in slugs:
        path = build_comment_path(content_type, slug)
        counter_stats = counter_stats_by_path.get(path)
        stats_by_slug[slug] = {
            "comment_count": counts_by_path.get(path, 0),
            "view_count": counter_stats.pageview_count if counter_stats is not None else None,
            "like_count": counter_stats.reaction_count if counter_stats is not None else 0,
        }
    return stats_by_slug


def _to_entry(
    item: ContentModel,
    content_type: str,
    engagement_stats: dict[str, dict[str, int | None]],
) -> ContentEntryRead:
    published_reference = item.published_at or item.created_at

    # Read type-specific fields directly from the model
    category = getattr(item, "category", None)
    mood = getattr(item, "mood", None)
    weather = getattr(item, "weather", None)
    poem = getattr(item, "poem", None)
    author_name = getattr(item, "author_name", None)
    source = getattr(item, "source", None)
    fallback_view_count = getattr(item, "view_count", 0) or 0
    stats = engagement_stats.get(item.slug, {})
    waline_view_count = stats.get("view_count")
    view_count = fallback_view_count if waline_view_count is None else waline_view_count

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
        comment_count=stats.get("comment_count", 0),
        like_count=stats.get("like_count", 0),
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
    items, total = repo.find_published(session, model, limit=limit, offset=offset)
    slugs = [item.slug for item in items]
    engagement_stats = _engagement_stats_by_slug(content_type, slugs)
    return ContentCollectionRead(
        items=[_to_entry(row, content_type, engagement_stats) for row in items],
        total=total,
        has_more=offset + limit < total,
    )


def _get_by_slug(session: Session, model: type[ContentModel], content_type: str, slug: str) -> ContentEntryRead:
    item = repo.find_by_slug(session, model, slug)
    if item is None:
        raise ResourceNotFound(f"{model.__name__} with slug '{slug}' was not found")
    engagement_stats = _engagement_stats_by_slug(content_type, [item.slug])
    return _to_entry(item, content_type, engagement_stats)


def list_public_posts(session: Session, limit: int = 20, offset: int = 0) -> ContentCollectionRead:
    return _list_entries(session, PostEntry, "posts", limit, offset)


def get_public_post(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, PostEntry, "posts", slug)


def list_public_diary_entries(session: Session, limit: int = 20, offset: int = 0) -> ContentCollectionRead:
    return _list_entries(session, DiaryEntry, "diary", limit, offset)


def get_public_diary_entry(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, DiaryEntry, "diary", slug)


def list_public_thoughts(session: Session, limit: int = 40, offset: int = 0) -> ContentCollectionRead:
    return _list_entries(session, ThoughtEntry, "thoughts", limit, offset)


def list_public_excerpts(session: Session, limit: int = 40, offset: int = 0) -> ContentCollectionRead:
    return _list_entries(session, ExcerptEntry, "excerpts", limit, offset)


def aggregate_tags(session: Session) -> list:
    """Cross-model tag aggregation with counts."""
    from aerisun.domain.content.schemas import TagInfo

    tag_counts = repo.count_by_tags(session)
    return sorted(
        [TagInfo(name=name, count=count) for name, count in tag_counts.items()],
        key=lambda t: t.count,
        reverse=True,
    )


def normalize_category_name(name: str) -> str:
    normalized = " ".join(name.split()).strip()
    if not normalized:
        raise ValidationError("分类名称不能为空")
    if len(normalized) > 80:
        raise ValidationError("分类名称不能超过 80 个字符")
    return normalized


def _normalize_and_sync_category(
    session: Session,
    data: dict,
    *,
    content_type: str | None,
) -> None:
    if "category" not in data:
        return

    raw_value = data.get("category")
    if raw_value is None:
        return

    if not isinstance(raw_value, str):
        raise ValidationError("分类名称格式不正确")

    normalized_name = " ".join(raw_value.split()).strip()
    data["category"] = normalized_name or None

    if normalized_name and content_type:
        create_managed_category(session, content_type=content_type, name=normalized_name)


def ensure_content_type(content_type: str) -> str:
    if content_type not in CONTENT_CATEGORY_TYPES:
        raise ValidationError("不支持的内容类型")
    return content_type


def _category_usage_count(session: Session, *, content_type: str, name: str) -> int:
    model = repo.CONTENT_MODELS[content_type]
    return session.query(func.count(model.id)).filter(model.category == name).scalar() or 0


def _to_category_read(session: Session, category: ContentCategory) -> ContentCategoryRead:
    return ContentCategoryRead(
        id=category.id,
        content_type=category.content_type,
        name=category.name,
        usage_count=_category_usage_count(
            session,
            content_type=category.content_type,
            name=category.name,
        ),
    )


def sync_managed_categories_from_content(session: Session, *, content_type: str | None = None) -> None:
    target_types = [content_type] if content_type else sorted(CONTENT_CATEGORY_TYPES)
    for current_type in target_types:
        ensure_content_type(current_type)
        existing_names = {category.name for category in repo.list_categories(session, content_type=current_type)}
        discovered_names = repo.list_distinct_content_categories(session, content_type=current_type)
        for name in discovered_names:
            normalized_name = normalize_category_name(name)
            if normalized_name in existing_names:
                continue
            repo.create_category(
                session,
                category_id=uuid_str(),
                content_type=current_type,
                name=normalized_name,
            )
            existing_names.add(normalized_name)


def list_managed_categories(session: Session, *, content_type: str | None = None) -> list[ContentCategoryRead]:
    if content_type is not None:
        ensure_content_type(content_type)
    sync_managed_categories_from_content(session, content_type=content_type)
    categories = [
        category
        for category in repo.list_categories(session, content_type=content_type)
        if category.content_type in CONTENT_CATEGORY_TYPES
    ]
    return [_to_category_read(session, category) for category in categories]


def create_managed_category(session: Session, *, content_type: str, name: str) -> ContentCategoryRead:
    category_type = ensure_content_type(content_type)
    normalized_name = normalize_category_name(name)
    existing = repo.get_category_by_name(session, content_type=category_type, name=normalized_name)
    if existing is not None:
        return _to_category_read(session, existing)
    category = repo.create_category(
        session,
        category_id=uuid_str(),
        content_type=category_type,
        name=normalized_name,
    )
    return _to_category_read(session, category)


def update_managed_category(session: Session, *, category_id: str, name: str) -> ContentCategoryRead:
    category = repo.get_category(session, category_id)
    if category is None:
        raise ResourceNotFound("Category not found")

    normalized_name = normalize_category_name(name)
    duplicate = repo.get_category_by_name(
        session,
        content_type=category.content_type,
        name=normalized_name,
    )
    if duplicate is not None and duplicate.id != category.id:
        raise ValidationError("该分类已存在")

    previous_name = category.name
    category = repo.update_category_name(session, category, name=normalized_name)
    if previous_name != normalized_name:
        model = repo.CONTENT_MODELS[category.content_type]
        items = session.query(model).filter(model.category == previous_name).all()
        for item in items:
            item.category = normalized_name
        session.commit()
    return _to_category_read(session, category)


def delete_managed_category(session: Session, *, category_id: str) -> None:
    category = repo.get_category(session, category_id)
    if category is None:
        raise ResourceNotFound("Category not found")
    if _category_usage_count(session, content_type=category.content_type, name=category.name) > 0:
        raise ValidationError("该分类仍在使用中，无法删除")
    repo.delete_category(session, category)
