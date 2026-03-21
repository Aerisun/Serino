from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aerisun.db import get_session
from aerisun.models import AdminSession, AdminUser
from aerisun.settings import get_settings

from .deps import get_current_admin
from .schemas import AdminUserRead, LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["admin-auth"])

SESSION_TTL_HOURS = 24


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    user = (
        session.query(AdminUser)
        .filter(AdminUser.username == payload.username)
        .first()
    )
    if user is None or not bcrypt.checkpw(
        payload.password.encode(), user.password_hash.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    settings = get_settings()
    ttl = getattr(settings, "session_ttl_hours", SESSION_TTL_HOURS)
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)

    admin_session = AdminSession(
        admin_user_id=user.id,
        session_token=token,
        expires_at=expires_at,
    )
    session.add(admin_session)
    session.commit()

    return LoginResponse(token=token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    # Delete the current session (the dep already validated it)
    # We need the token again; re-fetch via admin user's sessions
    sessions = (
        session.query(AdminSession)
        .filter(AdminSession.admin_user_id == admin.id)
        .all()
    )
    for s in sessions:
        session.delete(s)
    session.commit()


@router.get("/me", response_model=AdminUserRead)
def me(admin: AdminUser = Depends(get_current_admin)) -> AdminUserRead:
    return AdminUserRead.model_validate(admin)
