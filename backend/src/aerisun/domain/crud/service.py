"""Generic CRUD service — wraps repository calls with domain exceptions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

from aerisun.core.base import Base
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.service import normalize_content_update_state
from aerisun.domain.crud import repository as repo
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

CONTENT_PUBLICATION_MODELS = (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)
CONTENT_TYPE_BY_MODEL = {
    PostEntry: "posts",
    DiaryEntry: "diary",
    ThoughtEntry: "thoughts",
    ExcerptEntry: "excerpts",
}


def _is_public(obj: Any) -> bool:
    return getattr(obj, "visibility", None) == "public"


def _snapshot_is_public(snapshot: dict[str, Any]) -> bool:
    return snapshot["visibility"] == "public"


def _became_public(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    return not _snapshot_is_public(previous) and _snapshot_is_public(current)


def _dispatch_content_subscriptions_if_needed(
    model: type[Base],
    *,
    obj: Any | None = None,
    should_dispatch: bool | None = None,
) -> None:
    if model not in CONTENT_PUBLICATION_MODELS:
        return

    if should_dispatch is None and obj is not None:
        should_dispatch = _is_public(obj)

    if not should_dispatch:
        return

    from aerisun.domain.subscription.service import dispatch_content_subscription_notifications

    dispatch_content_subscription_notifications()


def _content_type_for_model(model: type[Base]) -> str:
    return CONTENT_TYPE_BY_MODEL.get(model, getattr(model, "__tablename__", model.__name__.lower()))


def _content_snapshot(obj: Any) -> dict[str, Any]:
    return {
        "item_id": str(getattr(obj, "id", "") or ""),
        "slug": str(getattr(obj, "slug", "") or ""),
        "title": str(getattr(obj, "title", "") or ""),
        "visibility": getattr(obj, "visibility", None),
    }


def list_items(
    session: Session,
    model: type[Base],
    *,
    page: int,
    page_size: int,
    read_schema: type[BaseModel],
    status_filter: str | None = None,
    visibility_filter: str | None = None,
    tag_filter: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> dict[str, Any]:
    items, total = repo.find_paginated(
        session,
        model,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        visibility_filter=visibility_filter,
        tag_filter=tag_filter,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        base_query_factory=base_query_factory,
    )
    return {
        "items": [read_schema.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_item(
    session: Session,
    model: type[Base],
    item_id: str,
    *,
    read_schema: type[BaseModel],
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> BaseModel:
    obj = repo.find_by_id(session, model, item_id, base_query_factory=base_query_factory)
    if obj is None:
        raise ResourceNotFound("Not found")
    return read_schema.model_validate(obj)


def create_item(
    session: Session,
    model: type[Base],
    payload: BaseModel,
    *,
    read_schema: type[BaseModel],
    prepare_data: Callable[[Session, dict[str, Any]], dict[str, Any]] | None = None,
) -> BaseModel:
    from aerisun.domain.automation.events import emit_content_created, emit_content_published

    data = payload.model_dump()
    obj = repo.create_one(session, model, data, prepare_data=prepare_data)
    snapshot = _content_snapshot(obj)
    content_type = _content_type_for_model(model)
    emit_content_created(
        session,
        content_type=content_type,
        item_id=snapshot["item_id"],
        slug=snapshot["slug"],
        title=snapshot["title"],
        visibility=snapshot["visibility"],
    )
    if _snapshot_is_public(snapshot):
        emit_content_published(
            session,
            content_type=content_type,
            item_id=snapshot["item_id"],
            slug=snapshot["slug"],
            title=snapshot["title"],
        )
        _dispatch_content_subscriptions_if_needed(model, obj=obj)
    return read_schema.model_validate(obj)


def update_item(
    session: Session,
    model: type[Base],
    item_id: str,
    payload: BaseModel,
    *,
    read_schema: type[BaseModel],
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
    prepare_data: Callable[[Session, Any, dict[str, Any]], dict[str, Any]] | None = None,
) -> BaseModel:
    from aerisun.domain.automation.events import (
        emit_content_published,
        emit_content_updated,
        emit_content_visibility_changed,
    )

    data = payload.model_dump(exclude_unset=True)
    obj = repo.find_by_id(session, model, item_id, base_query_factory=base_query_factory)
    if obj is None:
        raise ResourceNotFound("Not found")
    previous = _content_snapshot(obj)
    if prepare_data is not None:
        data = prepare_data(session, obj, data)
    obj = repo.update_one(session, obj, data)
    current = _content_snapshot(obj)
    content_type = _content_type_for_model(model)
    changed_fields = [
        key for key in data if key in {"slug", "title", "summary", "body", "visibility", "tags", "published_at"}
    ]
    emit_content_updated(
        session,
        content_type=content_type,
        item_id=current["item_id"],
        slug=current["slug"],
        title=current["title"],
        visibility=current["visibility"],
        changed_fields=changed_fields,
    )
    became_public = _became_public(previous, current)
    if became_public:
        emit_content_published(
            session,
            content_type=content_type,
            item_id=current["item_id"],
            slug=current["slug"],
            title=current["title"],
        )
    if previous["visibility"] != current["visibility"]:
        emit_content_visibility_changed(
            session,
            content_type=content_type,
            item_id=current["item_id"],
            slug=current["slug"],
            title=current["title"],
            visibility=current["visibility"],
        )
    if became_public:
        _dispatch_content_subscriptions_if_needed(model, should_dispatch=True)
    return read_schema.model_validate(obj)


def delete_item(
    session: Session,
    model: type[Base],
    item_id: str,
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> None:
    from aerisun.domain.automation.events import emit_content_deleted

    obj = repo.find_by_id(session, model, item_id, base_query_factory=base_query_factory)
    if obj is None:
        raise ResourceNotFound("Not found")
    snapshot = _content_snapshot(obj)
    repo.delete_one(session, obj)
    emit_content_deleted(
        session,
        content_type=_content_type_for_model(model),
        item_id=snapshot["item_id"],
        slug=snapshot["slug"],
        title=snapshot["title"],
    )


def bulk_delete_items(
    session: Session,
    model: type[Base],
    ids: list[str],
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> dict[str, int]:
    from aerisun.domain.automation.events import emit_content_bulk_deleted

    affected = repo.bulk_delete(session, model, ids, base_query_factory=base_query_factory)
    emit_content_bulk_deleted(
        session,
        content_type=_content_type_for_model(model),
        ids=ids,
        affected=affected,
    )
    return {"affected": affected}


def bulk_update_status_items(
    session: Session,
    model: type[Base],
    ids: list[str],
    status: str,
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> dict[str, int]:
    if not hasattr(model, "status"):
        raise ValidationError("Model does not support status")
    affected = repo.bulk_update_status(
        session,
        model,
        ids,
        status,
        base_query_factory=base_query_factory,
    )
    return {"affected": affected}


def bulk_update_visibility_items(
    session: Session,
    model: type[Base],
    ids: list[str],
    visibility: str,
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> dict[str, int]:
    from aerisun.domain.automation.events import emit_content_published, emit_content_visibility_changed

    if not hasattr(model, "visibility"):
        raise ValidationError("Model does not support visibility")
    if visibility not in {"public", "private"}:
        raise ValidationError("Visibility must be public or private")

    should_dispatch_subscriptions = False
    emitted_changes: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if model in CONTENT_PUBLICATION_MODELS:
        query = session.query(model) if base_query_factory is None else base_query_factory(session)
        objects = query.filter(model.id.in_(ids)).all()
        for obj in objects:
            previous = _content_snapshot(obj)
            normalized = normalize_content_update_state(session, obj, {"visibility": visibility})
            for key, value in normalized.items():
                if hasattr(type(obj), key):
                    setattr(obj, key, value)
            session.add(obj)
            current = _content_snapshot(obj)
            should_dispatch_subscriptions = should_dispatch_subscriptions or _became_public(previous, current)
            emitted_changes.append((previous, current))
        session.commit()
        affected = len(objects)
    else:
        affected = repo.bulk_update_visibility(
            session,
            model,
            ids,
            visibility,
            base_query_factory=base_query_factory,
        )

    content_type = _content_type_for_model(model)
    for previous, current in emitted_changes:
        if _became_public(previous, current):
            emit_content_published(
                session,
                content_type=content_type,
                item_id=current["item_id"],
                slug=current["slug"],
                title=current["title"],
            )
        if previous["visibility"] != current["visibility"]:
            emit_content_visibility_changed(
                session,
                content_type=content_type,
                item_id=current["item_id"],
                slug=current["slug"],
                title=current["title"],
                visibility=current["visibility"],
            )
    if should_dispatch_subscriptions:
        _dispatch_content_subscriptions_if_needed(model, should_dispatch=True)
    return {"affected": affected}
