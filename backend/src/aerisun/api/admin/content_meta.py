from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.schemas import (
    ContentCategoryCreate,
    ContentCategoryRead,
    ContentCategoryUpdate,
    TagInfo,
)
from aerisun.domain.content.service import (
    aggregate_tags,
    create_managed_category,
    delete_managed_category,
    list_managed_categories,
    update_managed_category,
)
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin

router = APIRouter(prefix="/content", tags=["admin-content-meta"])


@router.get("/tags", response_model=list[TagInfo], summary="聚合所有内容标签")
def list_tags(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[TagInfo]:
    return aggregate_tags(session)


@router.get(
    "/category-options",
    response_model=list[ContentCategoryRead],
    summary="获取内容分类列表",
    operation_id="list_content_categories",
)
def list_category_options(
    content_type: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[ContentCategoryRead]:
    return list_managed_categories(session, content_type=content_type)


@router.post(
    "/category-options",
    response_model=ContentCategoryRead,
    summary="创建内容分类",
    operation_id="create_content_category",
)
def create_category_option(
    payload: ContentCategoryCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ContentCategoryRead:
    return create_managed_category(
        session,
        content_type=payload.content_type,
        name=payload.name,
    )


@router.put(
    "/category-options/{category_id}",
    response_model=ContentCategoryRead,
    summary="更新内容分类",
    operation_id="update_content_category",
)
def update_category_option(
    category_id: str,
    payload: ContentCategoryUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ContentCategoryRead:
    return update_managed_category(session, category_id=category_id, name=payload.name)


@router.delete(
    "/category-options/{category_id}",
    summary="删除内容分类",
    operation_id="delete_content_category",
)
def delete_category_option(
    category_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    delete_managed_category(session, category_id=category_id)
