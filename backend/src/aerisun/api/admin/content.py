from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from aerisun.core.base import Base
from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin
from .schemas import BulkActionResponse, BulkDeleteRequest, BulkStatusRequest

# Columns that the list endpoint is allowed to sort by.
_ALLOWED_SORT_COLUMNS = {
    "created_at",
    "updated_at",
    "title",
    "published_at",
    "status",
    "slug",
}


def build_crud_router(
    model: type[Base],
    *,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    prefix: str,
    tag: str,
) -> APIRouter:
    """Factory that returns a full CRUD router for a given SQLAlchemy model."""

    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("/", response_model=dict, summary=f"获取{tag}列表")
    def list_items(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        status_filter: str | None = Query(default=None, alias="status"),
        tag: str | None = Query(default=None),
        search: str | None = Query(default=None),
        sort_by: str = Query(default="created_at"),
        sort_order: str = Query(default="desc"),
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """分页查询并返回列表数据。"""
        q = session.query(model)

        # --- filters ---
        if status_filter and hasattr(model, "status"):
            q = q.filter(model.status == status_filter)  # type: ignore[arg-type]
        if tag and hasattr(model, "tags"):
            q = q.filter(model.tags.contains(f'"{tag}"'))  # type: ignore[union-attr]
        if search and hasattr(model, "title"):
            pattern = f"%{search}%"
            clauses = [model.title.ilike(pattern)]  # type: ignore[union-attr]
            if hasattr(model, "body"):
                clauses.append(model.body.ilike(pattern))  # type: ignore[union-attr]
            if hasattr(model, "slug"):
                clauses.append(model.slug.ilike(pattern))  # type: ignore[union-attr]
            q = q.filter(or_(*clauses))

        total = q.count()

        # --- sorting ---
        col_name = sort_by if sort_by in _ALLOWED_SORT_COLUMNS else "created_at"
        col = getattr(model, col_name, None) or model.created_at  # type: ignore[union-attr]
        order_col = col.asc() if sort_order == "asc" else col.desc()

        # Pinned items first when the model supports it
        order_clauses = []
        if hasattr(model, "is_pinned"):
            order_clauses.append(model.is_pinned.desc())  # type: ignore[union-attr]
            if hasattr(model, "pin_order"):
                order_clauses.append(model.pin_order.asc())  # type: ignore[union-attr]
        order_clauses.append(order_col)

        items = q.order_by(*order_clauses).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [read_schema.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @router.post(
        "/",
        response_model=read_schema,
        status_code=status.HTTP_201_CREATED,
        summary=f"创建{tag}",
    )
    def create_item(
        payload: create_schema,  # type: ignore[valid-type]
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        """接收数据并创建一条新记录。"""
        data = {k: v for k, v in payload.model_dump().items() if hasattr(model, k)}
        obj = model(**data)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return read_schema.model_validate(obj)

    @router.get("/{item_id}", response_model=read_schema, summary=f"获取单条{tag}")
    def get_item(
        item_id: str,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        """根据 ID 获取单条记录详情。"""
        obj = session.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        return read_schema.model_validate(obj)

    @router.put("/{item_id}", response_model=read_schema, summary=f"更新{tag}")
    def update_item(
        item_id: str,
        payload: update_schema,  # type: ignore[valid-type]
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        """根据 ID 更新一条记录的字段。"""
        obj = session.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            if hasattr(model, key):
                setattr(obj, key, value)
        session.commit()
        session.refresh(obj)
        return read_schema.model_validate(obj)

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary=f"删除{tag}")
    def delete_item(
        item_id: str,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> None:
        """根据 ID 删除一条记录。"""
        obj = session.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        session.delete(obj)
        session.commit()

    # --- Bulk operations ---

    @router.post("/bulk-delete", response_model=BulkActionResponse, summary=f"批量删除{tag}")
    def bulk_delete(
        payload: BulkDeleteRequest,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        """根据 ID 列表批量删除记录。"""
        affected = (
            session.query(model)
            .filter(model.id.in_(payload.ids))  # type: ignore[union-attr]
            .delete(synchronize_session="fetch")
        )
        session.commit()
        return {"affected": affected}

    @router.post("/bulk-status", response_model=BulkActionResponse, summary=f"批量更新{tag}状态")
    def bulk_status(
        payload: BulkStatusRequest,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        """根据 ID 列表批量更新记录状态。"""
        if not hasattr(model, "status"):
            raise HTTPException(status_code=400, detail="Model does not support status")
        affected = (
            session.query(model)
            .filter(model.id.in_(payload.ids))  # type: ignore[union-attr]
            .update({"status": payload.status}, synchronize_session="fetch")
        )
        session.commit()
        return {"affected": affected}

    return router
