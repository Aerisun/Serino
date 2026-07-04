from __future__ import annotations

import re
from datetime import date, datetime
from typing import TypeVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.core.base import uuid_str
from aerisun.core.time import BEIJING_TZ, beijing_day_bounds, beijing_today, shanghai_now, to_beijing_datetime
from aerisun.domain.content import repository as repo
from aerisun.domain.content.models import (
    ContentCategory,
    DiaryEntry,
    ExcerptEntry,
    PostEntry,
    ThoughtEntry,
)
from aerisun.domain.content.schemas import (
    ContentCategoryRead,
    ContentCollectionRead,
    ContentEntryRead,
    ContentSummaryCollectionRead,
    ContentSummaryRead,
    ContentTitleSuggestionRead,
)
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.ops import repository as ops_repo
from aerisun.domain.waline.service import build_comment_path, count_records_by_urls, get_counter_stats_by_urls

ContentModel = TypeVar("ContentModel", PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)

CONTENT_CATEGORY_TYPES = {"posts", "thoughts", "excerpts"}
CONTENT_TYPES = {"posts", "diary", "thoughts", "excerpts"}
TAGLESS_CONTENT_TYPES = {"diary", "thoughts", "excerpts"}

CONTENT_VISIBILITY_VALUES = {"public", "private"}
MANAGED_MODEL_CONTENT_TYPES = {
    PostEntry: "posts",
    DiaryEntry: "diary",
    ThoughtEntry: "thoughts",
    ExcerptEntry: "excerpts",
}

DEFAULT_TITLE_PREFIXES = {
    "diary": "日记",
    "thoughts": "碎碎念",
    "excerpts": "文摘",
}
CHINESE_NUMERAL_DIGITS = "零一二三四五六七八九"


def _normalize_optional_text(
    value: object | None,
    *,
    field_label: str,
    collapse_whitespace: bool = True,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field_label}格式不正确")
    normalized = " ".join(value.split()) if collapse_whitespace else value.strip()
    return normalized or None


def _normalize_tags(value: object | None) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("标签格式不正确")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = str(item).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _to_chinese_numeral(value: int) -> str:
    if value <= 0:
        raise ValidationError("标题序号必须大于 0")
    if value < 10:
        return CHINESE_NUMERAL_DIGITS[value]
    if value < 20:
        suffix = "" if value == 10 else CHINESE_NUMERAL_DIGITS[value % 10]
        return f"十{suffix}"
    if value < 100:
        tens, ones = divmod(value, 10)
        prefix = f"{CHINESE_NUMERAL_DIGITS[tens]}十"
        return prefix if ones == 0 else f"{prefix}{CHINESE_NUMERAL_DIGITS[ones]}"
    if value < 1000:
        hundreds, remainder = divmod(value, 100)
        prefix = f"{CHINESE_NUMERAL_DIGITS[hundreds]}百"
        if remainder == 0:
            return prefix
        if remainder < 10:
            return f"{prefix}零{CHINESE_NUMERAL_DIGITS[remainder]}"
        return f"{prefix}{_to_chinese_numeral(remainder)}"
    return str(value)


def _from_chinese_numeral(value: str) -> int | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        parsed = int(normalized)
        return parsed if parsed > 0 else None
    if normalized in CHINESE_NUMERAL_DIGITS:
        parsed = CHINESE_NUMERAL_DIGITS.index(normalized)
        return parsed if parsed > 0 else None
    if "百" in normalized:
        hundreds_text, _, remainder_text = normalized.partition("百")
        hundreds = CHINESE_NUMERAL_DIGITS.find(hundreds_text)
        if hundreds <= 0:
            return None
        if not remainder_text:
            return hundreds * 100
        if remainder_text.startswith("零"):
            ones = CHINESE_NUMERAL_DIGITS.find(remainder_text[1:])
            return hundreds * 100 + ones if ones > 0 else None
        remainder = _from_chinese_numeral(remainder_text)
        return hundreds * 100 + remainder if remainder is not None else None
    if normalized.startswith("十"):
        suffix = normalized[1:]
        if not suffix:
            return 10
        ones = CHINESE_NUMERAL_DIGITS.find(suffix)
        return 10 + ones if ones > 0 else None
    if "十" in normalized:
        tens_text, _, ones_text = normalized.partition("十")
        tens = CHINESE_NUMERAL_DIGITS.find(tens_text)
        if tens <= 0:
            return None
        if not ones_text:
            return tens * 10
        ones = CHINESE_NUMERAL_DIGITS.find(ones_text)
        return tens * 10 + ones if ones > 0 else None
    return None


def _format_default_title_date_label(target_day: date) -> str:
    return f"{target_day.year % 100}.{target_day.month}.{target_day.day}."


def _format_diary_default_title_date_label(target_day: date) -> str:
    return f"{target_day.year % 100}年{target_day.month}月{target_day.day}日"


def _normalize_default_title_category(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value, field_label="分类")
    return normalized or None


def _title_sequence_for(content_type: str, title: str | None, target_day: date) -> int | None:
    if content_type not in {"thoughts", "excerpts"} or not title:
        return None
    prefix = DEFAULT_TITLE_PREFIXES[content_type]
    date_label = re.escape(_format_default_title_date_label(target_day))
    pattern = re.compile(
        rf"^{re.escape(prefix)}(?P<sequence>[零一二三四五六七八九十百\d]+)则 "
        rf"\({date_label}\)$"
    )
    match = pattern.match(title.strip())
    if match is None:
        return None
    return _from_chinese_numeral(match.group("sequence"))


def _is_likely_auto_title(content_type: str, title: str | None) -> bool:
    if not title:
        return False
    normalized = title.strip()
    if content_type == "diary":
        return re.match(r"^\d{1,2}年\d{1,2}月\d{1,2}日记$", normalized) is not None
    if content_type in {"thoughts", "excerpts"}:
        prefix = re.escape(DEFAULT_TITLE_PREFIXES[content_type])
        return (
            re.match(
                rf"^{prefix}[零一二三四五六七八九十百\d]+则 "
                r"\(\d{1,2}\.\d{1,2}\.\d{1,2}\.\)$",
                normalized,
            )
            is not None
        )
    return False


def _public_reference_day(value: datetime | None) -> date:
    return to_beijing_datetime(value or shanghai_now()).date()


def _resolve_default_title_reference_day(
    session: Session,
    *,
    content_type: str,
    item_id: str | None,
) -> date:
    if not item_id:
        return beijing_today()

    model = repo.CONTENT_MODELS.get(content_type)
    if model is None:
        raise ValidationError("不支持的内容类型")

    existing = session.query(model).filter(model.id == item_id).first()
    if existing is None:
        raise ValidationError("内容不存在")

    reference_time = getattr(existing, "published_at", None) or getattr(existing, "created_at", None)
    if reference_time is None:
        return beijing_today()
    return to_beijing_datetime(reference_time).date()


def _count_daily_title_candidates(
    session: Session,
    *,
    content_type: str,
    target_day: date,
    category: str | None = None,
    exclude_id: str | None = None,
) -> int:
    model = repo.CONTENT_MODELS.get(content_type)
    if model is None:
        raise ValidationError("不支持的内容类型")
    day_start, day_end = beijing_day_bounds(target_day)
    reference_time = func.coalesce(model.published_at, model.created_at)
    query = session.query(func.count(model.id)).filter(reference_time >= day_start, reference_time < day_end)
    if exclude_id:
        query = query.filter(model.id != exclude_id)
    if content_type in {"thoughts", "excerpts"}:
        normalized_category = _normalize_default_title_category(category)
        if normalized_category:
            query = query.filter(model.category == normalized_category)
        else:
            query = query.filter((model.category.is_(None)) | (model.category == ""))
    return query.scalar() or 0


def _max_title_sequence(
    session: Session,
    *,
    content_type: str,
    target_day: date,
    exclude_id: str | None = None,
) -> int:
    model = repo.CONTENT_MODELS.get(content_type)
    if model is None:
        raise ValidationError("不支持的内容类型")
    if content_type not in {"thoughts", "excerpts"}:
        return 0

    day_start, day_end = beijing_day_bounds(target_day)
    reference_time = func.coalesce(model.first_published_at, model.published_at, model.created_at)
    query = session.query(model).filter(reference_time >= day_start, reference_time < day_end)
    if exclude_id:
        query = query.filter(model.id != exclude_id)

    max_sequence = 0
    for item in query.all():
        sequence = _title_sequence_for(content_type, item.public_title or item.title, target_day)
        if sequence is not None:
            max_sequence = max(max_sequence, sequence)
    return max_sequence


def suggest_content_default_title(
    session: Session,
    *,
    content_type: str,
    category: str | None = None,
    item_id: str | None = None,
) -> ContentTitleSuggestionRead:
    prefix = DEFAULT_TITLE_PREFIXES.get(content_type)
    if prefix is None:
        raise ValidationError("仅支持为日记、碎碎念和文摘生成默认标题")

    existing = None
    if item_id:
        model = repo.CONTENT_MODELS.get(content_type)
        if model is None:
            raise ValidationError("不支持的内容类型")
        existing = session.query(model).filter(model.id == item_id).first()
        if existing is None:
            raise ValidationError("内容不存在")

    if existing is not None and getattr(existing, "public_title", None):
        public_title = str(existing.public_title)
        reference_day = _public_reference_day(existing.first_published_at)
        sequence = _title_sequence_for(content_type, public_title, reference_day) or 1
        return ContentTitleSuggestionRead(
            title=public_title,
            sequence=sequence,
            date_label=(
                _format_diary_default_title_date_label(reference_day)
                if content_type == "diary"
                else _format_default_title_date_label(reference_day)
            ),
        )

    target_day = _resolve_default_title_reference_day(
        session,
        content_type=content_type,
        item_id=item_id,
    )
    sequence = (
        _count_daily_title_candidates(
            session,
            content_type=content_type,
            target_day=target_day,
            category=category,
            exclude_id=item_id,
        )
        + 1
    )
    if content_type == "diary":
        date_label = _format_diary_default_title_date_label(target_day)
        title = f"{date_label}记"
    else:
        date_label = _format_default_title_date_label(target_day)
        title = f"{prefix}{_to_chinese_numeral(sequence)}则 ({date_label})"
    return ContentTitleSuggestionRead(
        title=title,
        sequence=sequence,
        date_label=date_label,
    )


def _all_existing_content_slugs(session: Session) -> set[str]:
    existing: set[str] = set()
    for model in repo.CONTENT_MODELS.values():
        existing.update(
            slug.strip()
            for slug in session.query(model.slug).all()
            for slug in [slug[0]]
            if isinstance(slug[0], str) and slug[0].strip()
        )
    return existing


def _generate_next_content_slug(session: Session) -> str:
    existing_slugs = _all_existing_content_slugs(session)
    next_value = max((int(slug) for slug in existing_slugs if slug.isdigit()), default=0) + 1
    while str(next_value) in existing_slugs:
        next_value += 1
    return str(next_value)


def _ensure_unique_slug(
    session: Session,
    slug: str,
    *,
    exclude_model: type[ContentModel] | None = None,
    exclude_id: str | None = None,
) -> None:
    for model in repo.CONTENT_MODELS.values():
        existing = session.query(model).filter(model.slug == slug).first()
        if existing is None:
            continue
        if exclude_model is model and getattr(existing, "id", None) == exclude_id:
            continue
        raise StateConflict(f"slug '{slug}' 已存在")


def _normalize_content_fields(
    session: Session,
    data: dict,
    *,
    content_type: str,
    existing: ContentModel | None = None,
) -> None:
    if content_type not in CONTENT_TYPES:
        raise ValidationError("不支持的内容类型")

    if "slug" in data:
        data["slug"] = _normalize_optional_text(data.get("slug"), field_label="slug", collapse_whitespace=False)
    if "title" in data:
        data["title"] = _normalize_optional_text(data.get("title"), field_label="标题")
    if "summary" in data:
        data["summary"] = _normalize_optional_text(data.get("summary"), field_label="摘要", collapse_whitespace=False)
    if "author_name" in data:
        data["author_name"] = _normalize_optional_text(data.get("author_name"), field_label="作者")
    if "source" in data:
        data["source"] = _normalize_optional_text(data.get("source"), field_label="来源", collapse_whitespace=False)

    if content_type in TAGLESS_CONTENT_TYPES:
        data["tags"] = []
    elif existing is None or "tags" in data:
        data["tags"] = _normalize_tags(data.get("tags"))

    if existing is None:
        if not data.get("title"):
            raise ValidationError("标题不能为空")
    elif "title" in data and not data.get("title"):
        raise ValidationError("标题不能为空")

    if existing is None:
        resolved_slug = data.get("slug") or _generate_next_content_slug(session)
        _ensure_unique_slug(session, resolved_slug)
        data["slug"] = resolved_slug
        return

    if "slug" not in data:
        return

    next_slug = data.get("slug")
    if not next_slug:
        data.pop("slug", None)
        return
    if next_slug == existing.slug:
        return
    _ensure_unique_slug(session, next_slug, exclude_model=type(existing), exclude_id=existing.id)


def _normalize_visibility(value: str | None, *, fallback: str = "private") -> str:
    return value if value in CONTENT_VISIBILITY_VALUES else fallback


def _build_auto_public_title(
    session: Session,
    *,
    content_type: str,
    target_time: datetime,
    exclude_id: str | None = None,
) -> str:
    target_day = _public_reference_day(target_time)
    if content_type == "diary":
        return f"{_format_diary_default_title_date_label(target_day)}记"
    if content_type not in {"thoughts", "excerpts"}:
        raise ValidationError("不支持的自动标题类型")
    sequence = (
        _max_title_sequence(
            session,
            content_type=content_type,
            target_day=target_day,
            exclude_id=exclude_id,
        )
        + 1
    )
    return f"{DEFAULT_TITLE_PREFIXES[content_type]}{_to_chinese_numeral(sequence)}则 ({_format_default_title_date_label(target_day)})"


def _resolve_public_title_for_first_publish(
    session: Session,
    *,
    content_type: str,
    title: str,
    published_at: datetime,
    exclude_id: str | None = None,
) -> str:
    if content_type in DEFAULT_TITLE_PREFIXES and _is_likely_auto_title(content_type, title):
        return _build_auto_public_title(
            session,
            content_type=content_type,
            target_time=published_at,
            exclude_id=exclude_id,
        )
    return title.strip()


def _is_public_visibility(visibility: str | None) -> bool:
    return visibility == "public"


def normalize_content_create_state(session: Session, data: dict) -> dict:
    normalized = dict(data)
    content_type = normalized.pop("_content_type", None)
    if not isinstance(content_type, str):
        raise ValidationError("不支持的内容类型")
    _normalize_content_fields(session, normalized, content_type=content_type)
    _normalize_and_sync_category(session, normalized, content_type=content_type)
    visibility = _normalize_visibility(normalized.get("visibility"))
    normalized["visibility"] = visibility
    if _is_public_visibility(visibility):
        published_at = normalized.get("published_at") or shanghai_now()
        normalized["published_at"] = published_at
        public_title = _resolve_public_title_for_first_publish(
            session,
            content_type=content_type,
            title=normalized["title"],
            published_at=published_at,
        )
        normalized["title"] = public_title
        normalized["public_title"] = public_title
        normalized["first_published_at"] = published_at
    return normalized


def normalize_content_update_state(session: Session, existing: ContentModel, patch: dict) -> dict:
    normalized = dict(patch)
    content_type = MANAGED_MODEL_CONTENT_TYPES.get(type(existing))
    if content_type is None:
        raise ValidationError("不支持的内容类型")
    _normalize_content_fields(session, normalized, content_type=content_type, existing=existing)
    _normalize_and_sync_category(
        session,
        normalized,
        content_type=content_type,
    )
    previous_visibility = _normalize_visibility(getattr(existing, "visibility", None), fallback="private")
    next_visibility = _normalize_visibility(
        normalized.get("visibility"),
        fallback=previous_visibility,
    )
    normalized["visibility"] = next_visibility

    was_public = _is_public_visibility(previous_visibility)
    will_be_public = _is_public_visibility(next_visibility)
    existing_public_title = getattr(existing, "public_title", None)
    existing_first_published_at = getattr(existing, "first_published_at", None)
    current_title = str(normalized.get("title") or getattr(existing, "title", "") or "").strip()
    current_published_at = (
        normalized.get("published_at") if "published_at" in normalized else getattr(existing, "published_at", None)
    )

    if was_public and not will_be_public:
        public_title = existing_public_title or str(getattr(existing, "title", "") or "").strip()
        first_published_at = existing_first_published_at or getattr(existing, "published_at", None) or shanghai_now()
        normalized["public_title"] = public_title
        normalized["first_published_at"] = first_published_at
        if "published_at" not in normalized:
            normalized["published_at"] = current_published_at or first_published_at
        return normalized

    if not was_public and will_be_public and existing_public_title:
        normalized["title"] = existing_public_title
        normalized["public_title"] = existing_public_title
        if existing_first_published_at is not None:
            normalized["first_published_at"] = existing_first_published_at
        if current_published_at is None or current_published_at == getattr(existing, "published_at", None):
            normalized["published_at"] = existing_first_published_at or getattr(existing, "published_at", None)
        return normalized

    if not was_public and will_be_public:
        published_at = current_published_at or shanghai_now()
        public_title = _resolve_public_title_for_first_publish(
            session,
            content_type=content_type,
            title=current_title,
            published_at=published_at,
            exclude_id=getattr(existing, "id", None),
        )
        normalized["title"] = public_title
        normalized["public_title"] = public_title
        normalized["first_published_at"] = published_at
        normalized["published_at"] = published_at
        return normalized

    if will_be_public:
        first_published_at = existing_first_published_at or current_published_at or shanghai_now()
        public_title = current_title or existing_public_title or getattr(existing, "title", "")
        normalized["public_title"] = public_title
        normalized["first_published_at"] = first_published_at
        if current_published_at is None:
            normalized["published_at"] = first_published_at
        return normalized

    if existing_public_title:
        normalized["public_title"] = existing_public_title
        if existing_first_published_at is not None:
            normalized["first_published_at"] = existing_first_published_at
        return normalized

    return normalized


def _estimate_read_time_for_length(value: int) -> str:
    return f"{max(1, round(value / 180))} 分钟"


def _estimate_read_time(value: str) -> str:
    return _estimate_read_time_for_length(len(value))


def _format_display_date(value: datetime | None) -> str | None:
    if value is None:
        return None

    reference = to_beijing_datetime(value)
    return f"{reference.year} 年 {reference.month} 月 {reference.day} 日"


def _format_relative_date(value: datetime | None) -> str | None:
    if value is None:
        return None

    reference = to_beijing_datetime(value)
    now = datetime.now(BEIJING_TZ)
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


def _engagement_stats_by_slug(
    session: Session,
    content_type: str,
    slugs: list[str],
) -> dict[str, dict[str, int | None]]:
    if not slugs:
        return {}

    paths = [build_comment_path(content_type, slug) for slug in slugs]
    counts_by_path = count_records_by_urls(urls=paths, status="approved")
    counter_stats_by_path = get_counter_stats_by_urls(urls=paths)
    visit_counts_by_path = ops_repo.count_successful_visit_records_by_paths(session, paths=paths)
    stats_by_slug: dict[str, dict[str, int | None]] = {}
    for slug in slugs:
        path = build_comment_path(content_type, slug)
        counter_stats = counter_stats_by_path.get(path)
        counter_view_count = counter_stats.pageview_count if counter_stats is not None else None
        visit_view_count = visit_counts_by_path.get(path)
        view_count_candidates = [value for value in (counter_view_count, visit_view_count) if value is not None]
        stats_by_slug[slug] = {
            "comment_count": counts_by_path.get(path, 0),
            "view_count": max(view_count_candidates) if view_count_candidates else None,
            "like_count": counter_stats.reaction_count if counter_stats is not None else 0,
        }
    return stats_by_slug


def _summary_fallback_from_body(value: str, *, max_length: int = 500) -> str | None:
    for paragraph in re.split(r"\n{2,}", value):
        normalized = " ".join(paragraph.split())
        if not normalized:
            continue
        if len(normalized) <= max_length:
            return normalized
        return normalized[: max_length - 1].rstrip() + "…"
    return None


def _content_summary_payload(
    item: ContentModel,
    content_type: str,
    engagement_stats: dict[str, dict[str, int | None]],
    *,
    include_read_time: bool,
    summary_fallback_body: str | None = None,
    read_time_body_length: int | None = None,
) -> dict:
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
    measured_view_count = stats.get("view_count")
    view_count = max(value for value in (fallback_view_count, measured_view_count) if value is not None)

    summary = item.summary
    if not (summary or "").strip() and summary_fallback_body:
        summary = _summary_fallback_from_body(summary_fallback_body)

    return {
        "slug": item.slug,
        "title": item.title,
        "summary": summary,
        "tags": item.tags,
        "visibility": item.visibility,
        "published_at": item.published_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "category": category,
        "read_time": (
            _estimate_read_time(item.body)
            if include_read_time
            else _estimate_read_time_for_length(read_time_body_length)
            if read_time_body_length is not None
            else None
        ),
        "display_date": _format_display_date(published_reference),
        "relative_date": _format_relative_date(published_reference),
        "view_count": view_count,
        "comment_count": stats.get("comment_count", 0),
        "like_count": stats.get("like_count", 0),
        "repost_count": 0,
        "mood": mood,
        "weather": weather,
        "poem": poem,
        "author": author_name,
        "source": source,
    }


def _to_summary_entry(
    item: ContentModel,
    content_type: str,
    engagement_stats: dict[str, dict[str, int | None]],
    *,
    summary_fallback_body: str | None = None,
    read_time_body_length: int | None = None,
) -> ContentSummaryRead:
    return ContentSummaryRead(
        **_content_summary_payload(
            item,
            content_type,
            engagement_stats,
            include_read_time=False,
            summary_fallback_body=summary_fallback_body,
            read_time_body_length=read_time_body_length,
        ),
    )


def _to_entry(
    item: ContentModel,
    content_type: str,
    engagement_stats: dict[str, dict[str, int | None]],
) -> ContentEntryRead:
    return ContentEntryRead(
        **_content_summary_payload(item, content_type, engagement_stats, include_read_time=True),
        body=item.body,
    )


def _list_entries(
    session: Session,
    model: type[ContentModel],
    content_type: str,
    limit: int,
    offset: int = 0,
    *,
    include_private: bool = False,
) -> ContentCollectionRead:
    items, total = repo.find_published(
        session,
        model,
        limit=limit,
        offset=offset,
        include_private=include_private,
    )
    slugs = [item.slug for item in items]
    engagement_stats = _engagement_stats_by_slug(session, content_type, slugs)
    return ContentCollectionRead(
        items=[_to_entry(row, content_type, engagement_stats) for row in items],
        total=total,
        has_more=offset + limit < total,
    )


def _list_summary_entries(
    session: Session,
    model: type[ContentModel],
    content_type: str,
    limit: int,
    offset: int = 0,
    *,
    include_private: bool = False,
) -> ContentSummaryCollectionRead:
    items, total = repo.find_published(
        session,
        model,
        limit=limit,
        offset=offset,
        include_private=include_private,
        load_body=False,
    )
    slugs = [item.slug for item in items]
    item_ids = [item.id for item in items]
    engagement_stats = _engagement_stats_by_slug(session, content_type, slugs)
    missing_summary_ids = [item.id for item in items if not (item.summary or "").strip()]
    body_lengths = repo.load_body_lengths_by_ids(session, model, item_ids)
    summary_fallback_bodies = repo.load_bodies_by_ids(session, model, missing_summary_ids)
    return ContentSummaryCollectionRead(
        items=[
            _to_summary_entry(
                row,
                content_type,
                engagement_stats,
                summary_fallback_body=summary_fallback_bodies.get(row.id),
                read_time_body_length=body_lengths.get(row.id),
            )
            for row in items
        ],
        total=total,
        has_more=offset + limit < total,
    )


def _get_by_slug(
    session: Session,
    model: type[ContentModel],
    content_type: str,
    slug: str,
    *,
    include_private: bool = False,
) -> ContentEntryRead:
    item = repo.find_by_slug(session, model, slug, include_private=include_private)
    if item is None:
        raise ResourceNotFound(f"{model.__name__} with slug '{slug}' was not found")
    engagement_stats = _engagement_stats_by_slug(session, content_type, [item.slug])
    return _to_entry(item, content_type, engagement_stats)


def list_public_posts(
    session: Session,
    limit: int = 20,
    offset: int = 0,
    *,
    include_private: bool = False,
) -> ContentSummaryCollectionRead:
    return _list_summary_entries(session, PostEntry, "posts", limit, offset, include_private=include_private)


def get_public_post(session: Session, slug: str, *, include_private: bool = False) -> ContentEntryRead:
    return _get_by_slug(session, PostEntry, "posts", slug, include_private=include_private)


def list_public_diary_entries(
    session: Session,
    limit: int = 20,
    offset: int = 0,
    *,
    include_private: bool = False,
) -> ContentSummaryCollectionRead:
    return _list_summary_entries(session, DiaryEntry, "diary", limit, offset, include_private=include_private)


def get_public_diary_entry(session: Session, slug: str, *, include_private: bool = False) -> ContentEntryRead:
    return _get_by_slug(session, DiaryEntry, "diary", slug, include_private=include_private)


def list_public_thoughts(
    session: Session,
    limit: int = 40,
    offset: int = 0,
    *,
    include_private: bool = False,
) -> ContentCollectionRead:
    return _list_entries(session, ThoughtEntry, "thoughts", limit, offset, include_private=include_private)


def list_public_excerpts(
    session: Session,
    limit: int = 40,
    offset: int = 0,
    *,
    include_private: bool = False,
) -> ContentCollectionRead:
    return _list_entries(session, ExcerptEntry, "excerpts", limit, offset, include_private=include_private)


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
