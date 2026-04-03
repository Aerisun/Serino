from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import get_current_site_session, get_current_site_user
from aerisun.core.db import get_session
from aerisun.core.rate_limit import RATE_AUTH_LOGIN, limiter
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.iam.schemas import (
    AdminEmailLoginRequest,
    AdminLoginOptionsRead,
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
    get_admin_profile,
    list_admin_sessions,
    revoke_admin_session,
    update_admin_profile,
)
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.service import (
    get_admin_login_options,
    resolve_admin_user_id_for_email,
    resolve_admin_user_id_for_site_session,
    validate_admin_email_password,
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


@router.get("/options", response_model=AdminLoginOptionsRead, summary="获取管理员登录方式")
def login_options(session: Session = Depends(get_session)) -> AdminLoginOptionsRead:
    return AdminLoginOptionsRead(**get_admin_login_options(session))


@router.post("/email", response_model=LoginResponse, summary="通过管理员邮箱登录")
@limiter.limit(RATE_AUTH_LOGIN)
def login_with_bound_email(
    request: Request,
    payload: AdminEmailLoginRequest,
    session: Session = Depends(get_session),
) -> LoginResponse:
    validate_admin_email_password(session, payload.password)
    admin_user_id = resolve_admin_user_id_for_email(session, payload.email)
    return create_admin_session(session, admin_user_id)


@router.post("/exchange-site-user", response_model=LoginResponse, summary="将当前前台管理员身份换成后台登录")
@limiter.limit(RATE_AUTH_LOGIN)
def exchange_site_user_login(
    request: Request,
    current_site_user: SiteUser = Depends(get_current_site_user),
    current_site_session: SiteUserSession = Depends(get_current_site_session),
    session: Session = Depends(get_session),
) -> LoginResponse:
    admin_user_id = resolve_admin_user_id_for_site_session(
        session,
        current_site_user,
        current_site_session,
    )
    return create_admin_session(session, admin_user_id)


@router.post("/logout", status_code=204, summary="管理员登出")
def logout(
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    destroy_admin_sessions(session, admin.id)


@router.get("/me", response_model=AdminUserRead, summary="获取当前管理员信息")
def me(admin: AdminUser = Depends(get_current_admin)) -> AdminUserRead:
    return get_admin_profile(admin)


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
