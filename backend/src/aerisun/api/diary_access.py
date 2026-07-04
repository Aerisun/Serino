from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import (
    get_current_site_session_optional,
    get_current_site_user,
    get_current_site_user_optional,
)
from aerisun.core.db import get_session
from aerisun.domain.diary_access.schemas import (
    DiaryAccessRequestCreate,
    DiaryAccessRequestRead,
    DiaryAccessStateRead,
)
from aerisun.domain.diary_access.service import get_diary_access_state, submit_diary_access_request
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession

router = APIRouter(prefix="/api/v1/site/diary-access", tags=["site"])


@router.get("/me", response_model=DiaryAccessStateRead, summary="获取当前访客日记查看权限")
def read_my_diary_access(
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> DiaryAccessStateRead:
    return get_diary_access_state(session, current_user, current_site_session)


@router.post(
    "/requests",
    response_model=DiaryAccessRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="提交日记查看申请",
)
def create_diary_access_request(
    payload: DiaryAccessRequestCreate,
    session: Session = Depends(get_session),
    current_user: SiteUser = Depends(get_current_site_user),
) -> DiaryAccessRequestRead:
    return submit_diary_access_request(session, current_user, payload)
