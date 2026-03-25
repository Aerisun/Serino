from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.engagement.service import (
    list_admin_comments,
    list_admin_guestbook,
    moderate_comment,
    moderate_guestbook_entry,
)
from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.schemas import CommentAdminRead, GuestbookAdminRead, ModerateAction

from .deps import get_current_admin
from .schemas import PaginatedResponse

router = APIRouter(prefix="/moderation", tags=["admin-moderation"])


@router.get("/comments", response_model=PaginatedResponse[CommentAdminRead], summary="获取评论审核列表")
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
    return list_admin_comments(
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


@router.post("/comments/{comment_id}/moderate", response_model=CommentAdminRead, summary="审核评论")
def moderate_comment_endpoint(
    comment_id: str,
    payload: ModerateAction,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    try:
        waline_id = int(comment_id)
    except ValueError as err:
        raise ResourceNotFound("Comment not found") from err
    result = moderate_comment(session, waline_id, payload.action, payload.reason)
    if result is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)
    return result


@router.get("/guestbook", response_model=PaginatedResponse[GuestbookAdminRead], summary="获取留言审核列表")
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
    return list_admin_guestbook(
        page=page,
        page_size=page_size,
        status=status_filter,
        path=path_filter,
        keyword=keyword_filter,
        author=author_filter,
        email=email_filter,
        sort=sort,
    )


@router.post("/guestbook/{entry_id}/moderate", response_model=GuestbookAdminRead, summary="审核留言")
def moderate_guestbook_endpoint(
    entry_id: str,
    payload: ModerateAction,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    try:
        waline_id = int(entry_id)
    except ValueError as err:
        raise ResourceNotFound("Guestbook entry not found") from err
    result = moderate_guestbook_entry(session, waline_id, payload.action, payload.reason)
    if result is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)
    return result
