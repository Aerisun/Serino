from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import get_current_site_user, get_current_site_user_optional
from aerisun.core.db import get_session
from aerisun.domain.site_auth.models import SiteUser
from aerisun.domain.site_auth.schemas import (
    EmailLoginRequest,
    EmailLoginResponse,
    OAuthStartResponse,
    SiteAuthAvatarCandidateBatchRead,
    SiteAuthProfileUpdateRequest,
    SiteAuthStateRead,
    SiteAuthUserRead,
)
from aerisun.domain.site_auth.service import (
    build_avatar_candidate_batch,
    build_oauth_authorization_url,
    complete_oauth_login,
    destroy_site_session,
    get_auth_state,
    login_with_email,
    update_site_user_profile,
)

base_router = APIRouter()
router = APIRouter(prefix="/api/v1/site-auth", tags=["site-auth"])


def _cookie_name() -> str:
    from aerisun.core.settings import get_settings

    return get_settings().public_session_cookie_name


def _request_is_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",", 1)[0].strip().lower() == "https"
    return request.url.scheme == "https"


def _set_session_cookie(response: Response, token: str, *, secure: bool) -> None:
    from aerisun.core.settings import get_settings

    settings = get_settings()
    response.set_cookie(
        key=settings.public_session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=settings.public_session_ttl_hours * 3600,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(_cookie_name(), path="/")


@base_router.get("/me", response_model=SiteAuthStateRead, summary="获取当前站点用户状态")
def read_site_auth_state(
    session: Session = Depends(get_session),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
) -> SiteAuthStateRead:
    return get_auth_state(session, current_user)


@base_router.get("/avatar-candidates", response_model=SiteAuthAvatarCandidateBatchRead, summary="获取头像候选")
def read_avatar_candidates(
    identity: str | None = Query(default=None),
    batch: int = Query(default=0, ge=0),
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
) -> SiteAuthAvatarCandidateBatchRead:
    resolved_identity = (identity or "").strip() or (current_user.email if current_user else "")
    if not resolved_identity:
        raise HTTPException(status_code=400, detail="请先提供邮箱或登录后再试。")
    return build_avatar_candidate_batch(resolved_identity, batch=batch)


@base_router.post("/email", response_model=EmailLoginResponse, summary="通过邮箱识别登录")
def email_login(
    request: Request,
    payload: EmailLoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> EmailLoginResponse:
    result, token = login_with_email(session, payload)
    if token:
        _set_session_cookie(response, token, secure=_request_is_secure(request))
    return result


@base_router.patch("/me", response_model=SiteAuthUserRead, summary="更新当前站点用户资料")
def update_my_profile(
    payload: SiteAuthProfileUpdateRequest,
    session: Session = Depends(get_session),
    current_user: SiteUser = Depends(get_current_site_user),
) -> SiteAuthUserRead:
    return update_site_user_profile(session, current_user, payload)


@base_router.post("/logout", status_code=204, summary="站点用户登出")
def logout(
    response: Response,
    session: Session = Depends(get_session),
    site_session: str | None = Cookie(default=None, alias=_cookie_name()),
) -> None:
    if site_session:
        destroy_site_session(session, site_session)
    _clear_session_cookie(response)


@base_router.get("/oauth/{provider}/start", response_model=OAuthStartResponse, summary="获取 OAuth 跳转地址")
def oauth_start(
    request: Request,
    provider: str,
    response: Response,
    return_to: str = Query(default="/"),
    session: Session = Depends(get_session),
) -> OAuthStartResponse:
    callback_url = str(request.url_for("oauth_callback", provider=provider))
    authorization_url, state_cookie = build_oauth_authorization_url(
        session,
        provider,
        return_to,
        callback_url=callback_url,
    )
    response.set_cookie(
        key="aerisun_site_oauth_state",
        value=state_cookie,
        httponly=True,
        samesite="lax",
        secure=_request_is_secure(request),
        max_age=600,
        path="/",
    )
    return OAuthStartResponse(authorization_url=authorization_url)


@base_router.get("/oauth/{provider}/callback", summary="处理 OAuth 回调")
def oauth_callback(
    request: Request,
    provider: str,
    code: str,
    state: str,
    oauth_state: str | None = Cookie(default=None, alias="aerisun_site_oauth_state"),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    callback_url = str(request.url_for("oauth_callback", provider=provider))
    token, return_to = complete_oauth_login(
        session,
        provider,
        code,
        state,
        oauth_state,
        callback_url=callback_url,
    )
    redirect_to = return_to if "?" in return_to else f"{return_to}?auth=success"
    response = RedirectResponse(url=redirect_to, status_code=302)
    response.delete_cookie("aerisun_site_oauth_state", path="/")
    _set_session_cookie(response, token, secure=_request_is_secure(request))
    return response


router.include_router(base_router)
