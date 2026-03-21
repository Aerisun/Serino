from __future__ import annotations

from typing import TypeVar

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from aerisun.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.schemas import ContentCollectionRead, ContentEntryRead

ContentModel = TypeVar("ContentModel", PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)


def _public_query(model: type[ContentModel]) -> Select[tuple[ContentModel]]:
    return (
        select(model)
        .where(model.status == "published", model.visibility == "public")
        .order_by(desc(model.published_at), desc(model.created_at))
    )


def _to_entry(item: ContentModel) -> ContentEntryRead:
    return ContentEntryRead.model_validate(item)


def _list_entries(session: Session, model: type[ContentModel], limit: int) -> ContentCollectionRead:
    rows = session.scalars(_public_query(model).limit(limit)).all()
    return ContentCollectionRead(items=[_to_entry(row) for row in rows])


def _get_by_slug(session: Session, model: type[ContentModel], slug: str) -> ContentEntryRead:
    item = session.scalars(
        _public_query(model).where(model.slug == slug).limit(1)
    ).first()
    if item is None:
        raise LookupError(f"{model.__name__} with slug '{slug}' was not found")
    return _to_entry(item)


def list_public_posts(session: Session, limit: int = 20) -> ContentCollectionRead:
    return _list_entries(session, PostEntry, limit)


def get_public_post(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, PostEntry, slug)


def list_public_diary_entries(session: Session, limit: int = 20) -> ContentCollectionRead:
    return _list_entries(session, DiaryEntry, limit)


def get_public_diary_entry(session: Session, slug: str) -> ContentEntryRead:
    return _get_by_slug(session, DiaryEntry, slug)


def list_public_thoughts(session: Session, limit: int = 40) -> ContentCollectionRead:
    return _list_entries(session, ThoughtEntry, limit)


def list_public_excerpts(session: Session, limit: int = 40) -> ContentCollectionRead:
    return _list_entries(session, ExcerptEntry, limit)
