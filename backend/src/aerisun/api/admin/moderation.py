from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.diary_access.models import DiaryAccessRequest
from aerisun.domain.diary_access.schemas import (
    DiaryAccessRequestAdminList,
    DiaryAccessRequestAdminRead,
    DiaryAccessRequestAdminUpdate,
)
from aerisun.domain.diary_access.service import (
    diary_private_enabled,
    list_diary_access_requests_admin,
    update_diary_access_request_admin,
)
from aerisun.domain.engagement.schemas import CommentFeedbackUpdate
from aerisun.domain.engagement.service import (
    list_admin_comments,
    list_admin_guestbook,
    mark_admin_comments_read,
    mark_admin_guestbook_read,
    moderate_comment,
    moderate_guestbook_entry,
    update_admin_comment_feedback,
)
from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.schemas import (
    CommentAdminRead,
    GuestbookAdminRead,
    ModerateAction,
    ModerationAttentionCounts,
    ModerationDiaryAttentionBucket,
    ModerationReadResult,
    ModerationReadUpdate,
)
from aerisun.domain.post_access.models import PostAccessRequest
from aerisun.domain.post_access.schemas import (
    PostAccessRequestAdminList,
    PostAccessRequestAdminRead,
    PostAccessRequestAdminUpdate,
)
from aerisun.domain.post_access.service import (
    list_post_access_requests_admin,
    post_access_approval_enabled,
    update_post_access_request_admin,
)
from aerisun.domain.waline.service import get_waline_moderation_attention_counts

from .deps import get_current_admin
from .schemas import PaginatedResponse

router = APIRouter(prefix="/moderation", tags=["admin-moderation"])


@router.get(
    "/attention-counts",
    response_model=ModerationAttentionCounts,
    summary="获取审核提醒统计",
)
def get_attention_counts(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ModerationAttentionCounts:
    counts = get_waline_moderation_attention_counts()
    diary_pending = 0
    if diary_private_enabled(session):
        diary_pending = int(
            session.scalar(
                select(func.count()).select_from(DiaryAccessRequest).where(DiaryAccessRequest.status == "pending")
            )
            or 0
        )

    post_pending = 0
    if post_access_approval_enabled(session):
        post_pending = int(
            session.scalar(
                select(func.count()).select_from(PostAccessRequest).where(PostAccessRequest.status == "pending")
            )
            or 0
        )

    comments = counts["comments"]
    guestbook = counts["guestbook"]
    return ModerationAttentionCounts(
        comments=comments,
        guestbook=guestbook,
        diary_access=ModerationDiaryAttentionBucket(pending=diary_pending),
        post_access=ModerationDiaryAttentionBucket(pending=post_pending),
        pending_total=comments["pending"] + guestbook["pending"] + diary_pending + post_pending,
        unread_total=comments["unread"] + guestbook["unread"] + diary_pending + post_pending,
    )


@router.get(
    "/diary-access-requests",
    response_model=DiaryAccessRequestAdminList,
    summary="获取日记查看申请列表",
)
def list_diary_access_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return list_diary_access_requests_admin(session, page=page, page_size=page_size)


@router.patch(
    "/diary-access-requests/{request_id}",
    response_model=DiaryAccessRequestAdminRead,
    summary="审核日记查看申请",
)
def update_diary_access_request(
    request_id: str,
    payload: DiaryAccessRequestAdminUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> DiaryAccessRequestAdminRead:
    return update_diary_access_request_admin(session, request_id, payload, admin)


@router.get(
    "/post-access-requests",
    response_model=PostAccessRequestAdminList,
    summary="获取文章查看申请列表",
)
def list_post_access_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return list_post_access_requests_admin(session, page=page, page_size=page_size)


@router.patch(
    "/post-access-requests/{request_id}",
    response_model=PostAccessRequestAdminRead,
    summary="审核文章查看申请",
)
def update_post_access_request(
    request_id: str,
    payload: PostAccessRequestAdminUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> PostAccessRequestAdminRead:
    return update_post_access_request_admin(session, request_id, payload, admin)


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
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return list_admin_comments(
        session=session,
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


@router.patch("/comments/read", response_model=ModerationReadResult, summary="标记评论已读")
def mark_comments_read(
    payload: ModerationReadUpdate,
    _admin: AdminUser = Depends(get_current_admin),
) -> ModerationReadResult:
    return ModerationReadResult(marked=mark_admin_comments_read(payload.ids))


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


@router.patch("/comments/{comment_id}/feedback", response_model=CommentAdminRead, summary="修改评论反馈设置")
def update_comment_feedback_endpoint(
    comment_id: str,
    payload: CommentFeedbackUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> CommentAdminRead:
    try:
        waline_id = int(comment_id)
    except ValueError as err:
        raise ResourceNotFound("Comment not found") from err
    return update_admin_comment_feedback(session, waline_id, payload)


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
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return list_admin_guestbook(
        session=session,
        page=page,
        page_size=page_size,
        status=status_filter,
        path=path_filter,
        keyword=keyword_filter,
        author=author_filter,
        email=email_filter,
        sort=sort,
    )


@router.patch("/guestbook/read", response_model=ModerationReadResult, summary="标记留言已读")
def mark_guestbook_read(
    payload: ModerationReadUpdate,
    _admin: AdminUser = Depends(get_current_admin),
) -> ModerationReadResult:
    return ModerationReadResult(marked=mark_admin_guestbook_read(payload.ids))


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
