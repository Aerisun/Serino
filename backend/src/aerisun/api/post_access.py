from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import (
    get_current_site_session_optional,
    get_current_site_user,
    get_current_site_user_optional,
)
from aerisun.core.db import get_session
from aerisun.domain.post_access.schemas import (
    PostAccessGrantedListRead,
    PostAccessRequestCreate,
    PostAccessRequestRead,
    PostAccessStateRead,
)
from aerisun.domain.post_access.service import (
    get_post_access_state,
    list_current_user_post_access,
    submit_post_access_request,
)
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession

router = APIRouter(prefix="/api/v1/site/post-access", tags=["site"])


@router.get("/me", response_model=PostAccessGrantedListRead, summary="获取当前访客有效文章权限")
def list_my_post_access(
    session: Session = Depends(get_session),
    current_user: SiteUser = Depends(get_current_site_user),
) -> PostAccessGrantedListRead:
    return list_current_user_post_access(session, current_user)


@router.get("/{slug}/me", response_model=PostAccessStateRead, summary="获取当前访客文章查看权限")
def read_my_post_access(
    slug: str,
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> PostAccessStateRead:
    return get_post_access_state(session, slug, current_user, current_site_session)


@router.post(
    "/{slug}/requests",
    response_model=PostAccessRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="提交文章查看申请",
)
def create_post_access_request(
    slug: str,
    payload: PostAccessRequestCreate,
    session: Session = Depends(get_session),
    current_user: SiteUser = Depends(get_current_site_user),
) -> PostAccessRequestRead:
    return submit_post_access_request(session, slug, current_user, payload)
