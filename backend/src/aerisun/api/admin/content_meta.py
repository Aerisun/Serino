from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.schemas import CategoryInfo, TagInfo
from aerisun.domain.content.service import aggregate_categories, aggregate_tags
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin

router = APIRouter(prefix="/content", tags=["admin-content-meta"])


@router.get("/tags", response_model=list[TagInfo], summary="聚合所有内容标签")
def list_tags(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[TagInfo]:
    return aggregate_tags(session)


@router.get("/categories", response_model=list[CategoryInfo], summary="聚合文章分类")
def list_categories(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[CategoryInfo]:
    return aggregate_categories(session)
