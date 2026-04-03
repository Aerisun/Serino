from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.service import validate_site_session, validate_site_session_token


def _cookie_name() -> str:
    return get_settings().public_session_cookie_name


def get_site_session_cookie_name() -> str:
    return _cookie_name()


def request_is_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",", 1)[0].strip().lower() == "https"
    return request.url.scheme == "https"


def set_site_session_cookie(response: Response, token: str, *, secure: bool) -> None:
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


def clear_site_session_cookie(response: Response) -> None:
    response.delete_cookie(_cookie_name(), path="/")


def get_current_site_user_optional(
    session: Session = Depends(get_session),
    site_session: str | None = Cookie(default=None, alias=_cookie_name()),
) -> SiteUser | None:
    if not site_session:
        return None
    try:
        return validate_site_session_token(session, site_session)
    except Exception:
        return None


def get_current_site_session_optional(
    session: Session = Depends(get_session),
    site_session: str | None = Cookie(default=None, alias=_cookie_name()),
) -> SiteUserSession | None:
    if not site_session:
        return None
    try:
        return validate_site_session(session, site_session)
    except Exception:
        return None


def get_current_site_session(
    current_site_session: SiteUserSession | None = Depends(get_current_site_session_optional),
) -> SiteUserSession:
    if current_site_session is None:
        raise HTTPException(status_code=401, detail="请先登录。")
    return current_site_session


def get_current_site_user(
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
) -> SiteUser:
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录。")
    return current_user
