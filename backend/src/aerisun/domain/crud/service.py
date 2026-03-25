"""Generic CRUD service — wraps repository calls with domain exceptions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Query as SAQuery, Session

from aerisun.core.base import Base
from aerisun.domain.crud import repository as repo
from aerisun.domain.exceptions import ResourceNotFound, ValidationError


def list_items(
    session: Session,
    model: type[Base],
    *,
    page: int,
    page_size: int,
    read_schema: type[BaseModel],
    status_filter: str | None = None,
    tag_filter: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> dict[str, Any]:
    items, total = repo.find_paginated(
        session, model,
        page=page, page_size=page_size,
        status_filter=status_filter, tag_filter=tag_filter,
        search=search, sort_by=sort_by, sort_order=sort_order,
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
    return read_schema.model_validate(obj)


def update_item(
    session: Session,
    model: type[Base],
    item_id: str,
    payload: BaseModel,
    *,
    read_schema: type[BaseModel],
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> BaseModel:
    data = payload.model_dump(exclude_unset=True)
    obj = repo.find_by_id(session, model, item_id, base_query_factory=base_query_factory)
    if obj is None:
        raise ResourceNotFound("Not found")
    obj = repo.update_one(session, obj, data)
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
    affected = repo.bulk_update_status(session, model, ids, status, base_query_factory=base_query_factory)
    return {"affected": affected}
