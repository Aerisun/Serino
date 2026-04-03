from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from sqlalchemy import Select, and_, desc, func, or_, select
from sqlalchemy.orm import Session

from aerisun.domain.content.models import (
    ContentCategory,
    DiaryEntry,
    ExcerptEntry,
    PostEntry,
    ThoughtEntry,
)

ContentModel = TypeVar("ContentModel", PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)

CONTENT_MODELS: dict[str, type] = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}


def _public_filter(model: type[ContentModel], *, include_archived: bool = False) -> Select:
    """Base query for public content, with optional owner-only archived items."""
    visibility_filter = and_(model.status == "published", model.visibility == "public")
    if include_archived:
        visibility_filter = or_(
            visibility_filter,
            and_(model.status == "archived", model.visibility == "private"),
        )
    return select(model).where(visibility_filter).order_by(desc(model.published_at), desc(model.created_at))


def find_published(
    session: Session,
    model: type[ContentModel],
    *,
    limit: int,
    offset: int = 0,
    include_archived: bool = False,
) -> tuple[list, int]:
    """Paginated query for public content. Returns (items, total)."""
    base = _public_filter(model, include_archived=include_archived)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(session.scalars(base.offset(offset).limit(limit)).all())
    return items, total


def find_by_slug(
    session: Session,
    model: type[ContentModel],
    slug: str,
    *,
    include_archived: bool = False,
):
    """Find a single public item by slug. Returns model or None."""
    return session.scalars(
        _public_filter(model, include_archived=include_archived).where(model.slug == slug).limit(1)
    ).first()


def search_across_models(session: Session, query_str: str, *, limit: int) -> list[tuple]:
    """Cross-model full-text search. Returns list of (model_instance, type_name)."""
    pattern = f"%{query_str}%"
    results = []
    content_types = [
        (PostEntry, "posts"),
        (DiaryEntry, "diary"),
        (ThoughtEntry, "thoughts"),
        (ExcerptEntry, "excerpts"),
    ]
    for model, type_name in content_types:
        rows = session.scalars(
            select(model)
            .where(
                model.status == "published",
                model.visibility == "public",
                or_(
                    model.title.ilike(pattern),
                    model.body.ilike(pattern),
                    model.summary.ilike(pattern) if hasattr(model, "summary") else False,
                ),
            )
            .order_by(model.published_at.desc().nullslast())
            .limit(limit)
        ).all()
        for row in rows:
            results.append((row, type_name))
    return results


def find_published_urls(session: Session, model: type[ContentModel]) -> list[tuple[str, datetime | None]]:
    """For sitemap: return list of (slug, updated_at) for published content."""
    rows = session.execute(
        select(model.slug, model.updated_at).where(
            model.status == "published",
            model.visibility == "public",
        )
    ).all()
    return [(slug, updated_at) for slug, updated_at in rows]


def count_by_tags(session: Session) -> dict[str, int]:
    """Cross-model tag counting."""
    import json as _json

    tag_counts: dict[str, int] = {}
    for model in (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry):
        rows = session.query(model.tags).filter(model.tags.isnot(None)).all()
        for (tags_json,) in rows:
            if not tags_json:
                continue
            if isinstance(tags_json, str):
                try:
                    tags_list = _json.loads(tags_json)
                except (_json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(tags_json, list):
                tags_list = tags_json
            else:
                continue
            for tag in tags_list:
                tag = str(tag).strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return tag_counts


def list_categories(session: Session, *, content_type: str | None = None) -> list[ContentCategory]:
    query = session.query(ContentCategory)
    if content_type:
        query = query.filter(ContentCategory.content_type == content_type)
    return list(query.order_by(ContentCategory.content_type.asc(), ContentCategory.name.asc()).all())


def list_distinct_content_categories(session: Session, *, content_type: str) -> list[str]:
    model = CONTENT_MODELS[content_type]
    rows = (
        session.query(model.category)
        .filter(model.category.isnot(None), model.category != "")
        .distinct()
        .order_by(model.category.asc())
        .all()
    )
    return [name for (name,) in rows if name]


def get_category(session: Session, category_id: str) -> ContentCategory | None:
    return session.query(ContentCategory).filter(ContentCategory.id == category_id).first()


def get_category_by_name(session: Session, *, content_type: str, name: str) -> ContentCategory | None:
    return (
        session.query(ContentCategory)
        .filter(ContentCategory.content_type == content_type, ContentCategory.name == name)
        .first()
    )


def create_category(session: Session, *, category_id: str, content_type: str, name: str) -> ContentCategory:
    category = ContentCategory(id=category_id, content_type=content_type, name=name)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def update_category_name(session: Session, category: ContentCategory, *, name: str) -> ContentCategory:
    category.name = name
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def delete_category(session: Session, category: ContentCategory) -> None:
    session.delete(category)
    session.commit()


def find_all_for_export(session: Session, model: type[ContentModel]) -> list:
    """Export: query all items ordered by created_at desc."""
    return list(session.query(model).order_by(model.created_at.desc()).all())


def upsert_by_slug(session: Session, model: type[ContentModel], slug: str, data: dict) -> tuple[object, bool]:
    """Import: upsert by slug. Returns (item, created). Caller must commit."""
    existing = session.query(model).filter(model.slug == slug).first()
    if existing:
        for k, v in data.items():
            if k != "slug":
                setattr(existing, k, v)
        return existing, False
    obj = model(**data)
    session.add(obj)
    return obj, True
