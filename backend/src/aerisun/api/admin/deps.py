from __future__ import annotations

from datetime import UTC, datetime

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminSession, AdminUser, ApiKey

_bearer = HTTPBearer()


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AdminUser:
    token = credentials.credentials
    admin_session = session.query(AdminSession).filter(AdminSession.session_token == token).first()
    if admin_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    now_utc = datetime.now(UTC)
    now = now_utc.replace(tzinfo=None) if admin_session.expires_at.tzinfo is None else now_utc
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


def require_api_key_scopes(*required_scopes: str):
    """Return a FastAPI dependency that validates an API key has the required scopes."""

    def dependency(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        session: Session = Depends(get_session),
    ) -> ApiKey:
        token = credentials.credentials
        prefix = token[:8]
        key = (
            session.query(ApiKey)
            .filter(ApiKey.key_prefix == prefix)
            .first()
        )
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        if not bcrypt.checkpw(token.encode(), key.hashed_secret.encode()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        missing = [s for s in required_scopes if s not in key.scopes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scopes: {', '.join(missing)}",
            )
        key.last_used_at = datetime.now(timezone.utc)
        session.commit()
        return key

    return dependency
