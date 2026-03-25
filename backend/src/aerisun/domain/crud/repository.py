"""Generic CRUD repository — reusable paginated, filtered, sorted queries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Query as SAQuery, Session

from aerisun.core.base import Base

_ALLOWED_SORT_COLUMNS = {
    "created_at", "updated_at", "title", "published_at", "status", "slug",
}


def _scoped_query(
    session: Session,
    model: type[Base],
    base_query_factory: Callable[[Session], SAQuery[Any]] | None,
) -> SAQuery[Any]:
    if base_query_factory is None:
        return session.query(model)
    return base_query_factory(session)


def find_paginated(
    session: Session,
    model: type[Base],
    *,
    page: int,
    page_size: int,
    status_filter: str | None = None,
    tag_filter: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> tuple[list[Any], int]:
    q = _scoped_query(session, model, base_query_factory)

    if status_filter and hasattr(model, "status"):
        q = q.filter(model.status == status_filter)
    if tag_filter and hasattr(model, "tags"):
        q = q.filter(model.tags.contains(f'"{tag_filter}"'))
    if search and hasattr(model, "title"):
        pattern = f"%{search}%"
        clauses = [model.title.ilike(pattern)]
        if hasattr(model, "body"):
            clauses.append(model.body.ilike(pattern))
        if hasattr(model, "slug"):
            clauses.append(model.slug.ilike(pattern))
        q = q.filter(or_(*clauses))

    total = q.count()

    col_name = sort_by if sort_by in _ALLOWED_SORT_COLUMNS else "created_at"
    col = getattr(model, col_name, None) or model.created_at
    order_col = col.asc() if sort_order == "asc" else col.desc()

    order_clauses: list = []
    if hasattr(model, "is_pinned"):
        order_clauses.append(model.is_pinned.desc())
        if hasattr(model, "pin_order"):
            order_clauses.append(model.pin_order.asc())
    order_clauses.append(order_col)

    items = q.order_by(*order_clauses).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def find_by_id(
    session: Session,
    model: type[Base],
    item_id: str,
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> Any | None:
    return _scoped_query(session, model, base_query_factory).filter(model.id == item_id).first()


def create_one(
    session: Session,
    model: type[Base],
    data: dict[str, Any],
    *,
    prepare_data: Callable[[Session, dict[str, Any]], dict[str, Any]] | None = None,
) -> Any:
    filtered = {k: v for k, v in data.items() if hasattr(model, k)}
    if prepare_data is not None:
        filtered = prepare_data(session, filtered)
    obj = model(**filtered)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def update_one(session: Session, obj: Any, data: dict[str, Any]) -> Any:
    for key, value in data.items():
        if hasattr(type(obj), key):
            setattr(obj, key, value)
    session.commit()
    session.refresh(obj)
    return obj


def delete_one(session: Session, obj: Any) -> None:
    session.delete(obj)
    session.commit()


def bulk_delete(
    session: Session,
    model: type[Base],
    ids: list[str],
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> int:
    affected = (
        _scoped_query(session, model, base_query_factory)
        .filter(model.id.in_(ids))
        .delete(synchronize_session="fetch")
    )
    session.commit()
    return affected


def bulk_update_status(
    session: Session,
    model: type[Base],
    ids: list[str],
    status: str,
    *,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
) -> int:
    affected = (
        _scoped_query(session, model, base_query_factory)
        .filter(model.id.in_(ids))
        .update({"status": status}, synchronize_session="fetch")
    )
    session.commit()
    return affected
