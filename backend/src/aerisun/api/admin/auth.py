from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.rate_limit import RATE_AUTH_LOGIN, limiter
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.iam.schemas import (
    AdminProfileUpdate,
    AdminSessionRead,
    AdminUserRead,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
)
from aerisun.domain.iam.service import (
    authenticate_admin,
    change_admin_password,
    create_admin_session,
    destroy_admin_sessions,
    list_admin_sessions,
    revoke_admin_session,
    update_admin_profile,
)

from .deps import get_current_admin

router = APIRouter(prefix="/auth", tags=["admin-auth"])


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return None


@router.post("/login", response_model=LoginResponse, summary="管理员登录")
@limiter.limit(RATE_AUTH_LOGIN)
def login(request: Request, payload: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    user = authenticate_admin(session, payload.username, payload.password)
    return create_admin_session(session, user.id)


@router.post("/logout", status_code=204, summary="管理员登出")
def logout(
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    destroy_admin_sessions(session, admin.id)


@router.get("/me", response_model=AdminUserRead, summary="获取当前管理员信息")
def me(admin: AdminUser = Depends(get_current_admin)) -> AdminUserRead:
    return AdminUserRead.model_validate(admin)


@router.put("/password", status_code=204, summary="修改密码")
def change_password(
    payload: PasswordChangeRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    change_admin_password(session, admin, payload.current_password, payload.new_password)


@router.put("/profile", response_model=AdminUserRead, summary="更新个人资料")
def update_profile_endpoint(
    payload: AdminProfileUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AdminUserRead:
    return update_admin_profile(session, admin, payload.username)


@router.get("/sessions", response_model=list[AdminSessionRead], summary="获取活跃会话列表")
def list_sessions_endpoint(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AdminSessionRead]:
    return list_admin_sessions(session, admin.id, current_token=_extract_token(request))


@router.delete("/sessions/{session_id}", status_code=204, summary="撤销指定会话")
def revoke_session(
    session_id: str,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    revoke_admin_session(session, admin.id, session_id)
