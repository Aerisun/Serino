from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.schemas import (
    ContentCategoryCreate,
    ContentCategoryRead,
    ContentCategoryUpdate,
    ContentTitleSuggestionRead,
    TagInfo,
)
from aerisun.domain.content.service import (
    aggregate_tags,
    create_managed_category,
    delete_managed_category,
    list_managed_categories,
    suggest_content_default_title,
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
    "/default-title",
    response_model=ContentTitleSuggestionRead,
    summary="获取内容默认标题",
    operation_id="get_default_content_title",
)
def get_default_title(
    content_type: Literal["diary", "thoughts", "excerpts"] = Query(description="内容类型"),
    category: str | None = Query(default=None, description="内容分类"),
    status: Literal["draft", "published", "archived"] | None = Query(default=None, description="内容状态"),
    item_id: str | None = Query(default=None, description="当前内容 ID"),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ContentTitleSuggestionRead:
    return suggest_content_default_title(
        session,
        content_type=content_type,
        category=category,
        status=status,
        item_id=item_id,
    )


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
