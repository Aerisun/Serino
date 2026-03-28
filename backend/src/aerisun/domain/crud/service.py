"""Generic CRUD service — wraps repository calls with domain exceptions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

from aerisun.core.base import Base
from aerisun.domain.content.service import resolve_content_bulk_state
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.crud import repository as repo
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

CONTENT_PUBLICATION_MODELS = (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry)


def _is_published_public(obj: Any) -> bool:
    return (
        getattr(obj, "status", None) == "published"
        and getattr(obj, "visibility", None) == "public"
    )


def _dispatch_content_subscriptions_if_needed(model: type[Base], *, obj: Any | None = None, status: str | None = None, visibility: str | None = None) -> None:
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
    data = payload.model_dump()
    obj = repo.create_one(session, model, data, prepare_data=prepare_data)
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
    data = payload.model_dump(exclude_unset=True)
    obj = repo.find_by_id(session, model, item_id, base_query_factory=base_query_factory)
    if obj is None:
        raise ResourceNotFound("Not found")
    if prepare_data is not None:
        data = prepare_data(session, obj, data)
    obj = repo.update_one(session, obj, data)
    _dispatch_content_subscriptions_if_needed(model, obj=obj)
    return read_schema.model_validate(obj)


def delete_item(
    session: Session,
    model: type[Base],
    item_id: str,
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> None:
    obj = repo.find_by_id(session, model, item_id, base_query_factory=base_query_factory)
    if obj is None:
        raise ResourceNotFound("Not found")
    repo.delete_one(session, obj)


def bulk_delete_items(
    session: Session,
    model: type[Base],
    ids: list[str],
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> dict[str, int]:
    affected = repo.bulk_delete(session, model, ids, base_query_factory=base_query_factory)
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
    return {"affected": affected}
