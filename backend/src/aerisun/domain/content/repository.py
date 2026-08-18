from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from sqlalchemy import Select, desc, func, or_, select
from sqlalchemy.orm import Session, load_only

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

_CATEGORY_POST_KINDS = {
    "posts": "manuscript",
    "notes": "note",
}


def _category_content_query(session: Session, content_type: str):
    if content_type in _CATEGORY_POST_KINDS:
        return PostEntry, session.query(PostEntry).filter(PostEntry.kind == _CATEGORY_POST_KINDS[content_type])
    model = CONTENT_MODELS[content_type]
    return model, session.query(model)


def _public_filter(
    model: type[ContentModel],
    *,
    include_private: bool = False,
    exclude_from_rss: bool = False,
    exclude_requires_approval: bool = False,
    kind: str | None = None,
    category: str | None = None,
) -> Select:
    """Base query for public content, with optional owner-only private items."""
    visibility_filter = model.visibility == "public"
    if include_private:
        visibility_filter = or_(visibility_filter, model.visibility == "private")
    query = select(model).where(visibility_filter)
    if exclude_from_rss and hasattr(model, "exclude_from_rss"):
        query = query.where(model.exclude_from_rss.is_(False))
    if exclude_requires_approval and hasattr(model, "requires_approval"):
        query = query.where(model.requires_approval.is_(False))
    if kind is not None and hasattr(model, "kind"):
        query = query.where(model.kind == kind)
    normalized_category = category.strip() if isinstance(category, str) else None
    if normalized_category:
        query = query.where(model.category == normalized_category)
    return query.order_by(desc(model.published_at), desc(model.created_at))


def _summary_load_attributes(model: type[ContentModel]) -> list:
    fields = [
        "id",
        "slug",
        "title",
        "summary",
        "category",
        "kind",
        "tags",
        "visibility",
        "published_at",
        "created_at",
        "updated_at",
        "view_count",
        "mood",
        "weather",
        "poem",
        "author_name",
        "source",
        "requires_approval",
    ]
    return [getattr(model, field) for field in fields if hasattr(model, field)]


def find_published(
    session: Session,
    model: type[ContentModel],
    *,
    limit: int,
    offset: int = 0,
    include_private: bool = False,
    load_body: bool = True,
    exclude_from_rss: bool = False,
    exclude_requires_approval: bool = False,
    kind: str | None = None,
    category: str | None = None,
) -> tuple[list, int]:
    """Paginated query for public content. Returns (items, total)."""
    base = _public_filter(
        model,
        include_private=include_private,
        exclude_from_rss=exclude_from_rss,
        exclude_requires_approval=exclude_requires_approval,
        kind=kind,
        category=category,
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    if not load_body:
        base = base.options(load_only(*_summary_load_attributes(model)))
    items = list(session.scalars(base.offset(offset).limit(limit)).all())
    return items, total


def find_published_category_stats(
    session: Session,
    model: type[ContentModel],
    *,
    include_private: bool = False,
    kind: str | None = None,
) -> tuple[int, list[tuple[str, int]]]:
    """Return one complete visible count and grouped non-empty category counts."""
    base = _public_filter(
        model,
        include_private=include_private,
        kind=kind,
    ).order_by(None)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.with_only_columns(model.category, func.count(model.id))
        .where(model.category.isnot(None), model.category != "")
        .group_by(model.category)
        .order_by(func.count(model.id).desc(), model.category.asc())
    ).all()
    return total, [(name, int(count)) for name, count in rows if name]


def load_bodies_by_ids(session: Session, model: type[ContentModel], ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    rows = session.execute(select(model.id, model.body).where(model.id.in_(ids))).all()
    return {item_id: body for item_id, body in rows}


def load_body_lengths_by_ids(session: Session, model: type[ContentModel], ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    rows = session.execute(select(model.id, func.length(model.body)).where(model.id.in_(ids))).all()
    return {item_id: int(length or 0) for item_id, length in rows}


def find_by_slug(
    session: Session,
    model: type[ContentModel],
    slug: str,
    *,
    include_private: bool = False,
    kind: str | None = None,
):
    """Find a single public item by slug. Returns model or None."""
    return session.scalars(
        _public_filter(model, include_private=include_private, kind=kind).where(model.slug == slug).limit(1)
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
    model, query = _category_content_query(session, content_type)
    rows = (
        query.filter(model.category.isnot(None), model.category != "")
        .with_entities(model.category)
        .distinct()
        .order_by(model.category.asc())
        .all()
    )
    return [name for (name,) in rows if name]


def count_category_usage(session: Session, *, content_type: str, name: str) -> int:
    model, query = _category_content_query(session, content_type)
    return query.filter(model.category == name).count()


def rename_category_on_content(session: Session, *, content_type: str, previous_name: str, name: str) -> None:
    model, query = _category_content_query(session, content_type)
    items = query.filter(model.category == previous_name).all()
    for item in items:
        item.category = name
    session.commit()


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
