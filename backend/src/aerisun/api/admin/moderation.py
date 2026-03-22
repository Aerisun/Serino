from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.models import ModerationRecord
from aerisun.domain.waline.service import (
    list_guestbook_records,
    list_waline_records,
    moderate_waline_record,
    parse_comment_path,
)

from .deps import get_current_admin
from .schemas import CommentAdminRead, GuestbookAdminRead, ModerateAction

router = APIRouter(prefix="/moderation", tags=["admin-moderation"])


def _comment_admin_read_from_waline(record) -> CommentAdminRead:
    content_type, content_slug = parse_comment_path(record.url)
    return CommentAdminRead(
        id=str(record.id),
        content_type=content_type,
        content_slug=content_slug,
        parent_id=str(record.pid) if record.pid is not None else None,
        author_name=record.nick or "访客",
        author_email=record.mail,
        body=record.comment,
        status=record.status,
        created_at=record.inserted_at,
        updated_at=record.updated_at,
    )


def _guestbook_admin_read_from_waline(record) -> GuestbookAdminRead:
    return GuestbookAdminRead(
        id=str(record.id),
        name=record.nick or "访客",
        email=record.mail,
        website=record.link,
        body=record.comment,
        status=record.status,
        created_at=record.inserted_at,
        updated_at=record.updated_at,
    )


@router.get("/comments", response_model=dict, summary="获取评论审核列表")
def list_comments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    path_filter: str | None = Query(default=None, alias="path"),
    surface_filter: str | None = Query(default=None, alias="surface"),
    keyword_filter: str | None = Query(default=None, alias="keyword"),
    author_filter: str | None = Query(default=None, alias="author"),
    email_filter: str | None = Query(default=None, alias="email"),
    sort: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    _session: Session = Depends(get_session),
) -> dict[str, Any]:
    """分页查询待审核或全部评论，支持多维筛选。"""
    items, total = list_waline_records(
        page=page,
        page_size=page_size,
        status=status_filter,
        path=path_filter,
        surface=surface_filter,
        keyword=keyword_filter,
        author=author_filter,
        email=email_filter,
        sort=sort,
    )
    return {
        "items": [_comment_admin_read_from_waline(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/comments/{comment_id}/moderate",
    response_model=CommentAdminRead,
    summary="审核评论",
)
def moderate_comment(
    comment_id: str,
    payload: ModerateAction,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """对指定评论执行通过、拒绝或删除操作。"""
    try:
        waline_id = int(comment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Comment not found") from exc

    if payload.action not in {"approve", "reject", "delete"}:
        raise HTTPException(status_code=400, detail="Invalid action")

    result = moderate_waline_record(record_id=waline_id, action=payload.action)
    if payload.action == "delete":
        if result is None:
            raise HTTPException(status_code=404, detail="Comment not found")
        record = ModerationRecord(
            target_type="comment",
            target_id=comment_id,
            action="delete",
            reason=payload.reason,
        )
        session.add(record)
        session.commit()
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    if result is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    record = ModerationRecord(
        target_type="comment",
        target_id=comment_id,
        action=payload.action,
        reason=payload.reason,
    )
    session.add(record)
    session.commit()
    return _comment_admin_read_from_waline(result)


@router.get("/guestbook", response_model=dict, summary="获取留言审核列表")
def list_guestbook(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    path_filter: str | None = Query(default=None, alias="path"),
    keyword_filter: str | None = Query(default=None, alias="keyword"),
    author_filter: str | None = Query(default=None, alias="author"),
    email_filter: str | None = Query(default=None, alias="email"),
    sort: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    _session: Session = Depends(get_session),
) -> dict[str, Any]:
    """分页查询留言板条目，支持状态和关键词筛选。"""
    items, total = list_guestbook_records(
        page=page,
        page_size=page_size,
        status=status_filter,
        path=path_filter,
        keyword=keyword_filter,
        author=author_filter,
        email=email_filter,
        sort=sort,
    )
    return {
        "items": [_guestbook_admin_read_from_waline(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/guestbook/{entry_id}/moderate",
    response_model=GuestbookAdminRead,
    summary="审核留言",
)
def moderate_guestbook(
    entry_id: str,
    payload: ModerateAction,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """对指定留言执行通过、拒绝或删除操作。"""
    try:
        waline_id = int(entry_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail="Guestbook entry not found"
        ) from exc

    if payload.action not in {"approve", "reject", "delete"}:
        raise HTTPException(status_code=400, detail="Invalid action")

    result = moderate_waline_record(record_id=waline_id, action=payload.action)
    if payload.action == "delete":
        if result is None:
            raise HTTPException(status_code=404, detail="Guestbook entry not found")
        record = ModerationRecord(
            target_type="guestbook",
            target_id=entry_id,
            action="delete",
            reason=payload.reason,
        )
        session.add(record)
        session.commit()
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    if result is None:
        raise HTTPException(status_code=404, detail="Guestbook entry not found")

    record = ModerationRecord(
        target_type="guestbook",
        target_id=entry_id,
        action=payload.action,
        reason=payload.reason,
    )
    session.add(record)
    session.commit()
    return _guestbook_admin_read_from_waline(result)
