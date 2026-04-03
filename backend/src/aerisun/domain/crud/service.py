"""Generic CRUD service — wraps repository calls with domain exceptions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

from aerisun.core.base import Base
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.service import resolve_content_bulk_state
from aerisun.domain.crud import repository as repo
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

CONTENT_PUBLICATION_MODELS = (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)
CONTENT_TYPE_BY_MODEL = {
    PostEntry: "posts",
    DiaryEntry: "diary",
    ThoughtEntry: "thoughts",
    ExcerptEntry: "excerpts",
}


def _is_published_public(obj: Any) -> bool:
    return getattr(obj, "status", None) == "published" and getattr(obj, "visibility", None) == "public"


def _dispatch_content_subscriptions_if_needed(
    model: type[Base], *, obj: Any | None = None, status: str | None = None, visibility: str | None = None
) -> None:
    if model not in CONTENT_PUBLICATION_MODELS:
        return

    should_dispatch = False
    if obj is not None:
        should_dispatch = _is_published_public(obj)
    elif status is not None:
        should_dispatch = status == "published" and visibility == "public"

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
        "status": getattr(obj, "status", None),
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
        status=snapshot["status"],
        visibility=snapshot["visibility"],
    )
    if snapshot["status"] == "published" and snapshot["visibility"] == "public":
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
        emit_content_archived,
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
        key
        for key in data
        if key in {"slug", "title", "summary", "body", "status", "visibility", "tags", "published_at"}
    ]
    emit_content_updated(
        session,
        content_type=content_type,
        item_id=current["item_id"],
        slug=current["slug"],
        title=current["title"],
        status=current["status"],
        visibility=current["visibility"],
        changed_fields=changed_fields,
    )
    if (
        previous["status"] != current["status"]
        and current["status"] == "published"
        and current["visibility"] == "public"
    ):
        emit_content_published(
            session,
            content_type=content_type,
            item_id=current["item_id"],
            slug=current["slug"],
            title=current["title"],
        )
    if previous["status"] != current["status"] and current["status"] == "archived":
        emit_content_archived(
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
    _dispatch_content_subscriptions_if_needed(model, obj=obj)
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
    from aerisun.domain.automation.events import emit_content_status_changed

    if not hasattr(model, "status"):
        raise ValidationError("Model does not support status")
    visibility: str | None = None
    normalized_status = status
    if hasattr(model, "visibility"):
        normalized_status, visibility = resolve_content_bulk_state(status)
    affected = repo.bulk_update_status(
        session,
        model,
        ids,
        normalized_status,
        visibility=visibility,
        base_query_factory=base_query_factory,
    )
    _dispatch_content_subscriptions_if_needed(
        model,
        status=normalized_status,
        visibility=visibility or "public",
    )
    emit_content_status_changed(
        session,
        content_type=_content_type_for_model(model),
        ids=ids,
        status=normalized_status,
        visibility=visibility,
        affected=affected,
    )
    return {"affected": affected}
