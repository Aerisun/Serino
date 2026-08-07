from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.exceptions import AuthenticationFailed
from aerisun.domain.iam import repository as iam_repo
from aerisun.domain.iam.models import AdminSession, AdminUser
from aerisun.domain.iam.service import validate_admin_session, validate_session_token

_bearer = HTTPBearer()


@dataclass(frozen=True, slots=True)
class AuthenticatedAdminSession:
    admin: AdminUser
    session: AdminSession


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AdminUser:
    return validate_session_token(session, credentials.credentials)


def get_authenticated_admin_session(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AuthenticatedAdminSession:
    admin_session = iam_repo.find_session_by_token(session, credentials.credentials)
    if admin_session is None:
        raise AuthenticationFailed("Invalid or expired session token")
    admin = validate_admin_session(session, admin_session)
    return AuthenticatedAdminSession(admin=admin, session=admin_session)
