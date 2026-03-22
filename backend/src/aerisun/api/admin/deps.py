from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.models import AdminSession, AdminUser

_bearer = HTTPBearer()


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AdminUser:
    token = credentials.credentials
    admin_session = (
        session.query(AdminSession)
        .filter(AdminSession.session_token == token)
        .first()
    )
    if admin_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    now = datetime.utcnow() if admin_session.expires_at.tzinfo is None else datetime.now(timezone.utc)
    if admin_session.expires_at < now:
        session.delete(admin_session)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    user = session.get(AdminUser, admin_session.admin_user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user
