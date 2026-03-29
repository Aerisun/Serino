from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

from aerisun.core.base import Base
from aerisun.core.db import get_session
from aerisun.domain.crud import service as crud_service
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.config_revisions import create_config_revision

from .deps import get_current_admin
from .schemas import BulkActionResponse, BulkDeleteRequest, BulkStatusRequest, PaginatedResponse


def build_crud_router(
    model: type[Base],
    *,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    prefix: str,
    tag: str,
    base_query_factory: Callable[[Session], SAQuery[Any]] | None = None,
    prepare_create_data: Callable[[Session, dict[str, Any]], dict[str, Any]] | None = None,
    prepare_update_data: Callable[[Session, Any, dict[str, Any]], dict[str, Any]] | None = None,
    config_resource_key: str | None = None,
    capture_before: Callable[[Session], Any] | None = None,
    capture_after: Callable[[Session], Any] | None = None,
    build_revision_summary: Callable[[str, Any, Any], str | None] | None = None,
) -> APIRouter:
    """Factory that returns a full CRUD router for a given SQLAlchemy model."""

    router = APIRouter(prefix=prefix, tags=[tag])
    resource = prefix.strip("/").replace("/", "_")

    @router.get(
        "/", response_model=PaginatedResponse[read_schema], summary=f"获取{tag}列表", operation_id=f"list_{resource}"
    )
    def list_items(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        status_filter: str | None = Query(default=None, alias="status"),
        visibility_filter: str | None = Query(default=None, alias="visibility"),
        tag: str | None = Query(default=None),
        search: str | None = Query(default=None),
        sort_by: str = Query(default="created_at"),
        sort_order: str = Query(default="desc"),
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        return crud_service.list_items(
            session,
            model,
            page=page,
            page_size=page_size,
            read_schema=read_schema,
            status_filter=status_filter,
            visibility_filter=visibility_filter,
            tag_filter=tag,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            base_query_factory=base_query_factory,
        )

    @router.post(
        "/",
        response_model=read_schema,
        status_code=status.HTTP_201_CREATED,
        summary=f"创建{tag}",
        operation_id=f"create_{resource}",
    )
    def create_item(
        payload: create_schema,  # type: ignore[valid-type]
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        before_snapshot = capture_before(session) if config_resource_key and capture_before is not None else None
        result = crud_service.create_item(
            session,
            model,
            payload,
            read_schema=read_schema,
            prepare_data=prepare_create_data,
        )
        if config_resource_key and capture_before is not None:
            after_snapshot = (capture_after or capture_before)(session)
            create_config_revision(
                session,
                actor_id=_admin.id,
                resource_key=config_resource_key,
                operation="create",
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                summary_override=(
                    build_revision_summary("create", before_snapshot, after_snapshot)
                    if build_revision_summary
                    else None
                ),
            )
        return result

    @router.get("/{item_id}", response_model=read_schema, summary=f"获取单条{tag}", operation_id=f"get_{resource}")
    def get_item(
        item_id: str,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        return crud_service.get_item(
            session,
            model,
            item_id,
            read_schema=read_schema,
            base_query_factory=base_query_factory,
        )

    @router.put("/{item_id}", response_model=read_schema, summary=f"更新{tag}", operation_id=f"update_{resource}")
    def update_item(
        item_id: str,
        payload: update_schema,  # type: ignore[valid-type]
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        before_snapshot = capture_before(session) if config_resource_key and capture_before is not None else None
        result = crud_service.update_item(
            session,
            model,
            item_id,
            payload,
            read_schema=read_schema,
            base_query_factory=base_query_factory,
            prepare_data=prepare_update_data,
        )
        if config_resource_key and capture_before is not None:
            after_snapshot = (capture_after or capture_before)(session)
            create_config_revision(
                session,
                actor_id=_admin.id,
                resource_key=config_resource_key,
                operation="update",
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                summary_override=(
                    build_revision_summary("update", before_snapshot, after_snapshot)
                    if build_revision_summary
                    else None
                ),
            )
        return result

    @router.delete(
        "/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary=f"删除{tag}", operation_id=f"delete_{resource}"
    )
    def delete_item(
        item_id: str,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> None:
        before_snapshot = capture_before(session) if config_resource_key and capture_before is not None else None
        crud_service.delete_item(session, model, item_id, base_query_factory=base_query_factory)
        if config_resource_key and capture_before is not None:
            after_snapshot = (capture_after or capture_before)(session)
            create_config_revision(
                session,
                actor_id=_admin.id,
                resource_key=config_resource_key,
                operation="delete",
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                summary_override=(
                    build_revision_summary("delete", before_snapshot, after_snapshot)
                    if build_revision_summary
                    else None
                ),
            )

    @router.post(
        "/bulk-delete",
        response_model=BulkActionResponse,
        summary=f"批量删除{tag}",
        operation_id=f"bulk_delete_{resource}",
    )
    def bulk_delete(
        payload: BulkDeleteRequest,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        return crud_service.bulk_delete_items(session, model, payload.ids, base_query_factory=base_query_factory)

    @router.post(
        "/bulk-status",
        response_model=BulkActionResponse,
        summary=f"批量更新{tag}状态",
        operation_id=f"bulk_status_{resource}",
    )
    def bulk_status(
        payload: BulkStatusRequest,
        _admin: AdminUser = Depends(get_current_admin),
        session: Session = Depends(get_session),
    ) -> Any:
        return crud_service.bulk_update_status_items(
            session,
            model,
            payload.ids,
            payload.status,
            base_query_factory=base_query_factory,
        )

    return router
