from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.models import (
    DiaryEntry,
    ExcerptEntry,
    PostEntry,
    ThoughtEntry,
)
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin

router = APIRouter(prefix="/content", tags=["admin-content-meta"])


class TagInfo(BaseModel):
    name: str
    count: int


class CategoryInfo(BaseModel):
    name: str
    count: int


@router.get("/tags", response_model=list[TagInfo], summary="聚合所有内容标签")
def list_tags(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[TagInfo]:
    """跨所有内容表聚合标签及其使用次数。"""
    tag_counts: dict[str, int] = {}
    for model in (PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry):
        rows = session.query(model.tags).filter(model.tags.isnot(None)).all()
        for (tags_json,) in rows:
            if not tags_json:
                continue
            # tags is stored as JSON array string or Python list
            if isinstance(tags_json, str):
                try:
                    tags_list = json.loads(tags_json)
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(tags_json, list):
                tags_list = tags_json
            else:
                continue
            for tag in tags_list:
                tag = str(tag).strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return sorted(
        [TagInfo(name=name, count=count) for name, count in tag_counts.items()],
        key=lambda t: t.count,
        reverse=True,
    )


@router.get("/categories", response_model=list[CategoryInfo], summary="聚合文章分类")
def list_categories(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[CategoryInfo]:
    """聚合文章的分类及其数量。"""
    rows = (
        session.query(PostEntry.category, func.count(PostEntry.id))
        .filter(PostEntry.category.isnot(None), PostEntry.category != "")
        .group_by(PostEntry.category)
        .order_by(func.count(PostEntry.id).desc())
        .all()
    )
    return [CategoryInfo(name=name, count=count) for name, count in rows]
