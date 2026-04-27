from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import (
    get_current_site_session_optional,
    get_current_site_user,
    get_current_site_user_optional,
)
from aerisun.api.public_schemas import CommentImageUploadResponse
from aerisun.core.db import get_session
from aerisun.core.rate_limit import RATE_WRITE_ENGAGEMENT, RATE_WRITE_REACTION, comment_image_upload_rate_limit, limiter
from aerisun.domain.engagement.schemas import (
    CommentCollectionRead,
    CommentCreate,
    CommentCreateResponse,
    GuestbookCollectionRead,
    GuestbookCreate,
    GuestbookCreateResponse,
    ReactionCreate,
    ReactionRead,
)
from aerisun.domain.engagement.service import (
    create_public_comment,
    create_public_guestbook_entry,
    list_public_comments,
    list_public_guestbook_entries,
    read_public_reaction,
    register_public_reaction,
    remove_public_reaction,
)
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession

base_router = APIRouter()
router = APIRouter(prefix="/api/v1/site-interactions", tags=["site-interactions"])


@base_router.get("/guestbook", response_model=GuestbookCollectionRead, summary="获取留言板")
def read_guestbook(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> GuestbookCollectionRead:
    return list_public_guestbook_entries(session, page=page, page_size=page_size)


@base_router.post("/guestbook", response_model=GuestbookCreateResponse, summary="提交留言")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_guestbook(
    request: Request,
    payload: GuestbookCreate,
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> GuestbookCreateResponse:
    return create_public_guestbook_entry(
        session,
        payload,
        current_user=current_user,
        current_site_session=current_site_session,
    )


@base_router.get("/comments/{content_type}/{slug}", response_model=CommentCollectionRead, summary="获取内容评论")
def read_comments(
    content_type: str,
    slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> CommentCollectionRead:
    return list_public_comments(session, content_type, slug, page=page, page_size=page_size)


@base_router.post("/comments/{content_type}/{slug}", response_model=CommentCreateResponse, summary="发表评论")
@limiter.limit(RATE_WRITE_ENGAGEMENT)
def create_comment(
    request: Request,
    content_type: str,
    slug: str,
    payload: CommentCreate,
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> CommentCreateResponse:
    return create_public_comment(
        session,
        content_type,
        slug,
        payload,
        current_user=current_user,
        current_site_session=current_site_session,
    )


@base_router.post("/reactions", response_model=ReactionRead, summary="提交互动反应")
@limiter.limit(RATE_WRITE_REACTION)
def create_reaction(
    request: Request,
    payload: ReactionCreate,
    session: Session = Depends(get_session),
) -> ReactionRead:
    return register_public_reaction(session, payload)


@base_router.get(
    "/reactions/{content_type}/{slug}/{reaction_type}",
    response_model=ReactionRead,
    summary="查询反应计数",
)
def read_reaction(
    content_type: str,
    slug: str,
    reaction_type: str,
    client_token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> ReactionRead:
    return read_public_reaction(session, content_type, slug, reaction_type, client_token=client_token)


@base_router.delete(
    "/reactions/{content_type}/{slug}/{reaction_type}",
    response_model=ReactionRead,
    summary="取消互动反应",
)
@limiter.limit(RATE_WRITE_REACTION)
def delete_reaction(
    request: Request,
    content_type: str,
    slug: str,
    reaction_type: str,
    client_token: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
) -> ReactionRead:
    return remove_public_reaction(
        session,
        content_type=content_type,
        content_slug=slug,
        reaction_type=reaction_type,
        client_token=client_token,
    )


@base_router.post("/comment-image", response_model=CommentImageUploadResponse, summary="评论图片上传")
@limiter.limit(comment_image_upload_rate_limit)
def upload_comment_image(
    request: Request,
    file: UploadFile,
    session: Session = Depends(get_session),
    current_user: SiteUser = Depends(get_current_site_user),
) -> dict:
    from aerisun.domain.exceptions import PayloadTooLarge
    from aerisun.domain.media.service import get_comment_image_upload_limit, save_comment_image

    upload_limit = get_comment_image_upload_limit(session)
    content = file.file.read(upload_limit + 1)
    if len(content) > upload_limit:
        raise PayloadTooLarge("图片过大，请压缩后重试")
    url = save_comment_image(
        session,
        content,
        file.filename or "img",
        file.content_type,
        uploader_id=current_user.id,
    )
    return {"errno": 0, "data": {"url": url}}


router.include_router(base_router)
