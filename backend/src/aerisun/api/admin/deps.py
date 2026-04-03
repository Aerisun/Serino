from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.iam.service import ensure_admin_console_access, validate_session_token

_bearer = HTTPBearer()


def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AdminUser:
    cached_admin = getattr(request.state, "current_admin", None)
    cached_token = getattr(request.state, "current_admin_token", None)
    if cached_admin is not None and cached_token == credentials.credentials:
        return cached_admin

    admin = validate_session_token(session, credentials.credentials)
    request.state.current_admin = admin
    request.state.current_admin_token = credentials.credentials
    return admin


def require_admin_console_access(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    ensure_admin_console_access(admin)
    return admin
