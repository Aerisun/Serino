from __future__ import annotations

from typing import Any, Type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.models import AdminUser, Base

from .deps import get_current_admin


def build_crud_router(
    model: Type[Base],
    *,
    create_schema: Type[BaseModel],
    update_schema: Type[BaseModel],
    read_schema: Type[BaseModel],
    prefix: str,
    tag: str,
) -> APIRouter:
    """Factory that returns a full CRUD router for a given SQLAlchemy model."""

    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("/", response_model=dict)
    def list_items(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        status_filter: str | None = Query(default=None, alias="status"),
        tag: str | None = Query(default=None),
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        q = session.query(model)
        if status_filter and hasattr(model, "status"):
            q = q.filter(model.status == status_filter)  # type: ignore[arg-type]
        if tag and hasattr(model, "tags"):
            # SQLite JSON: check if tags array contains the value
            q = q.filter(model.tags.contains(f'"{tag}"'))  # type: ignore[union-attr]
        total = q.count()
        items = q.order_by(model.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()  # type: ignore[union-attr]
        return {
            "items": [read_schema.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @router.post("/", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    def create_item(
        payload: create_schema,  # type: ignore[valid-type]
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        obj = model(**payload.model_dump())
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return read_schema.model_validate(obj)

    @router.get("/{item_id}", response_model=read_schema)
    def get_item(
        item_id: str,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        obj = session.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        return read_schema.model_validate(obj)

    @router.put("/{item_id}", response_model=read_schema)
    def update_item(
        item_id: str,
        payload: update_schema,  # type: ignore[valid-type]
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        obj = session.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        session.commit()
        session.refresh(obj)
        return read_schema.model_validate(obj)

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(
        item_id: str,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> None:
        obj = session.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        session.delete(obj)
        session.commit()

    return router
