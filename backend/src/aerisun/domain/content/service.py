from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from aerisun.models import Comment, DiaryEntry, ExcerptEntry, PostEntry, Reaction, ThoughtEntry
from aerisun.schemas import ContentCollectionRead, ContentEntryRead

ContentModel = TypeVar("ContentModel", PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)

POST_CATEGORY_MAP: dict[str, str] = {
    "design-system": "设计",
    "frontend": "设计",
    "css": "技术",
    "performance": "技术",
    "react": "技术",
    "animation": "技术",
    "essay": "随想",
    "career": "随想",
}

CONTENT_PRESENTATION: dict[str, dict[str, dict[str, object]]] = {
    "posts": {
        "from-zero-design-system": {
            "category": "设计",
            "view_count": 1247,
            "comment_count": 18,
            "like_count": 42,
        },
        "liquid-glass-css-notes": {
            "category": "技术",
            "view_count": 3082,
            "comment_count": 24,
            "like_count": 56,
        },
        "why-i-choose-indie-design": {
            "category": "随想",
            "view_count": 892,
            "comment_count": 31,
            "like_count": 28,
        },
        "react-19-design-pattern-shifts": {
            "category": "技术",
            "view_count": 2156,
            "comment_count": 12,
            "like_count": 34,
        },
        "typographic-rhythm-and-spacing": {
            "category": "设计",
            "view_count": 1873,
            "comment_count": 15,
            "like_count": 29,
        },
        "framer-motion-page-transitions": {
            "category": "技术",
            "view_count": 4210,
            "comment_count": 37,
            "like_count": 61,
        },
        "solo-workflow-tools-and-rhythm": {
            "category": "随想",
            "view_count": 625,
            "comment_count": 8,
            "like_count": 17,
        },
        "dark-mode-design-details": {
            "category": "设计",
            "view_count": 3140,
            "comment_count": 26,
            "like_count": 48,
        },
    },
    "diary": {
        "spring-equinox-and-warm-light": {
            "weather": "sunny",
            "mood": "☀️",
            "poem": "春风如贵客，一到便繁华。——袁枚",
        },
        "rain-day-and-lofi": {
            "weather": "rainy",
            "mood": "🌧️",
            "poem": "小楼一夜听春雨，深巷明朝卖杏花。——陆游",
        },
        "windy-library-day": {
            "weather": "windy",
            "mood": "🍃",
            "poem": "解落三秋叶，能开二月花。——李峤",
        },
        "evening-tram-and-orange-sky": {
            "weather": "cloudy",
            "mood": "🌇",
            "poem": "落霞与孤鹜齐飞，秋水共长天一色。——王勃",
        },
        "quiet-sunday-cleanup": {
            "weather": "sunny",
            "mood": "🧺",
            "poem": "偷得浮生半日闲。——李涉",
        },
        "midnight-css-and-tea": {
            "weather": "rainy",
            "mood": "🍵",
            "poem": "何当共剪西窗烛，却话巴山夜雨时。——李商隐",
        },
        "bookstore-after-rain": {
            "weather": "cloudy",
            "mood": "📚",
            "poem": "纸上得来终觉浅，绝知此事要躬行。——陆游",
        },
    },
    "thoughts": {
        "spacing-rhythm-note": {
            "mood": "🎨",
            "like_count": 24,
            "comment_count": 5,
            "repost_count": 2,
        },
        "less-but-better-note": {
            "mood": "💭",
            "like_count": 47,
            "comment_count": 8,
            "repost_count": 6,
        },
        "frontend-as-craft": {
            "mood": "☕",
            "like_count": 53,
            "comment_count": 9,
            "repost_count": 4,
        },
        "ui-is-editing": {
            "mood": "✂️",
            "like_count": 19,
            "comment_count": 4,
            "repost_count": 1,
        },
        "soft-motion-note": {
            "mood": "🌫️",
            "like_count": 35,
            "comment_count": 6,
            "repost_count": 3,
        },
        "tiny-delight-matters": {
            "mood": "✨",
            "like_count": 27,
            "comment_count": 3,
            "repost_count": 2,
        },
        "interface-is-tone": {
            "mood": "🫧",
            "like_count": 31,
            "comment_count": 5,
            "repost_count": 2,
        },
        "shipping-beats-polish": {
            "mood": "🛠️",
            "like_count": 22,
            "comment_count": 4,
            "repost_count": 1,
        },
    },
    "excerpts": {
        "harmony-in-blank-space": {
            "author": "李欧梵",
            "source": "《中国现代文学与现代性十讲》",
        },
        "good-design-note": {
            "author": "Dieter Rams",
            "source": "Less but Better",
        },
        "repeat-has-power": {
            "author": "村上春树",
            "source": "《我的职业是小说家》",
        },
        "slow-work-note": {
            "author": "约翰·伯格",
            "source": "《观看之道》",
        },
        "poetry-and-interface": {
            "author": "原研哉",
            "source": "《设计中的设计》",
        },
        "honest-materials": {
            "author": "彼得·卒姆托",
            "source": "《思考建筑》",
        },
        "quiet-systems": {
            "author": "唐纳德·诺曼",
            "source": "《设计心理学》",
        },
    },
}


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


def _resolve_category(item: ContentModel, content_type: str, metadata: dict[str, object]) -> str | None:
    if content_type != "posts":
        return None

    explicit_category = metadata.get("category")
    if isinstance(explicit_category, str) and explicit_category:
        return explicit_category

    first_tag = item.tags[0] if item.tags else ""
    if not first_tag:
        return "内容"

    return POST_CATEGORY_MAP.get(first_tag, first_tag)


def _comment_counts_by_slug(session: Session, content_type: str, slugs: list[str]) -> dict[str, int]:
    if not slugs:
        return {}

    rows = session.execute(
        select(Comment.content_slug, func.count(Comment.id))
        .where(
            Comment.content_type == content_type,
            Comment.content_slug.in_(slugs),
            Comment.status == "approved",
        )
        .group_by(Comment.content_slug)
    ).all()
    return {slug: count for slug, count in rows}


def _like_counts_by_slug(session: Session, content_type: str, slugs: list[str]) -> dict[str, int]:
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
    metadata = CONTENT_PRESENTATION.get(content_type, {}).get(item.slug, {})

    repost_count = metadata.get("repost_count")
    view_count = metadata.get("view_count")
    comment_count = metadata.get("comment_count")
    like_count = metadata.get("like_count")
    published_reference = item.published_at or item.created_at

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
        category=_resolve_category(item, content_type, metadata),
        read_time=_estimate_read_time(item.body),
        display_date=_format_display_date(published_reference),
        relative_date=_format_relative_date(published_reference),
        view_count=view_count if isinstance(view_count, int) else 0,
        comment_count=comment_count if isinstance(comment_count, int) else comment_counts.get(item.slug, 0),
        like_count=like_count if isinstance(like_count, int) else like_counts.get(item.slug, 0),
        repost_count=repost_count if isinstance(repost_count, int) else 0,
        mood=metadata.get("mood") if isinstance(metadata.get("mood"), str) else None,
        weather=metadata.get("weather") if isinstance(metadata.get("weather"), str) else None,
        poem=metadata.get("poem") if isinstance(metadata.get("poem"), str) else None,
        author=metadata.get("author") if isinstance(metadata.get("author"), str) else None,
        source=metadata.get("source") if isinstance(metadata.get("source"), str) else None,
    )


def _list_entries(
    session: Session,
    model: type[ContentModel],
    content_type: str,
    limit: int,
) -> ContentCollectionRead:
    rows = session.scalars(_public_query(model).limit(limit)).all()
    slugs = [row.slug for row in rows]
    comment_counts = _comment_counts_by_slug(session, content_type, slugs)
    like_counts = _like_counts_by_slug(session, content_type, slugs)
    return ContentCollectionRead(
        items=[_to_entry(row, content_type, comment_counts, like_counts) for row in rows]
    )


def _get_by_slug(session: Session, model: type[ContentModel], content_type: str, slug: str) -> ContentEntryRead:
    item = session.scalars(
        _public_query(model).where(model.slug == slug).limit(1)
    ).first()
    if item is None:
        raise LookupError(f"{model.__name__} with slug '{slug}' was not found")
    comment_counts = _comment_counts_by_slug(session, content_type, [item.slug])
    like_counts = _like_counts_by_slug(session, content_type, [item.slug])
    return _to_entry(item, content_type, comment_counts, like_counts)


def list_public_posts(session: Session, limit: int = 20) -> ContentCollectionRead:
    return _list_entries(session, PostEntry, "posts", limit)


def get_public_post(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, PostEntry, "posts", slug)


def list_public_diary_entries(session: Session, limit: int = 20) -> ContentCollectionRead:
    return _list_entries(session, DiaryEntry, "diary", limit)


def get_public_diary_entry(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, DiaryEntry, "diary", slug)


def list_public_thoughts(session: Session, limit: int = 40) -> ContentCollectionRead:
    return _list_entries(session, ThoughtEntry, "thoughts", limit)


def list_public_excerpts(session: Session, limit: int = 40) -> ContentCollectionRead:
    return _list_entries(session, ExcerptEntry, "excerpts", limit)
