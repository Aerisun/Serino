from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.core.time import shanghai_now
from aerisun.domain.exceptions import AuthenticationFailed, PermissionDenied
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession

SESSION_TTL_HOURS = 24 * 30


def create_site_session(
    session: Session,
    site_user_id: str,
    ttl_hours: int | None = None,
    *,
    admin_verified_provider: str | None = None,
) -> str:
    from aerisun.domain.automation.events import emit_site_user_session_created

    settings = get_settings()
    ttl = ttl_hours or getattr(settings, "public_session_ttl_hours", SESSION_TTL_HOURS)
    token = secrets.token_urlsafe(64)
    expires_at = shanghai_now() + timedelta(hours=ttl)
    repo.create_session(
        session,
        site_user_id=site_user_id,
        token=token,
        admin_verified_provider=(admin_verified_provider or "").strip().lower() or None,
        expires_at=expires_at,
    )
    session.commit()
    emit_site_user_session_created(session, site_user_id=site_user_id)
    return token


def validate_site_session(session: Session, token: str) -> SiteUserSession:
    site_session = repo.find_session_by_token(session, token)
    if site_session is None:
        raise AuthenticationFailed("Invalid or expired session token")
    now_current = shanghai_now()
    now = now_current.replace(tzinfo=None) if site_session.expires_at.tzinfo is None else now_current
    if site_session.expires_at < now:
        session.delete(site_session)
        session.commit()
        raise AuthenticationFailed("Session expired")
    return site_session


def validate_site_session_token(session: Session, token: str) -> SiteUser:
    site_session = validate_site_session(session, token)
    user = repo.find_user_by_id(session, site_session.site_user_id)
    if user is None or not user.is_active:
        raise PermissionDenied("User not found or inactive")
    return user


def destroy_site_session(session: Session, token: str) -> None:
    from aerisun.domain.automation.events import emit_site_user_session_deleted

    existing = repo.find_session_by_token(session, token)
    if existing is None:
        return
    site_user_id = existing.site_user_id
    repo.delete_session(session, existing)
    session.commit()
    emit_site_user_session_deleted(session, site_user_id=site_user_id)
