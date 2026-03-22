from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.iam.models import AdminSession, AdminUser

from .deps import get_current_admin
from .schemas import (
    AdminProfileUpdate,
    AdminSessionRead,
    AdminUserRead,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
)

router = APIRouter(prefix="/auth", tags=["admin-auth"])

SESSION_TTL_HOURS = 24


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return None


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest, session: Session = Depends(get_session)
) -> LoginResponse:
    user = (
        session.query(AdminUser).filter(AdminUser.username == payload.username).first()
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
    expires_at = datetime.now(UTC) + timedelta(hours=ttl)

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
    sessions = (
        session.query(AdminSession).filter(AdminSession.admin_user_id == admin.id).all()
    )
    for s in sessions:
        session.delete(s)
    session.commit()


@router.get("/me", response_model=AdminUserRead)
def me(admin: AdminUser = Depends(get_current_admin)) -> AdminUserRead:
    return AdminUserRead.model_validate(admin)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    if not bcrypt.checkpw(
        payload.current_password.encode(), admin.password_hash.encode()
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    admin.password_hash = bcrypt.hashpw(
        payload.new_password.encode(), bcrypt.gensalt()
    ).decode()
    session.commit()


@router.put("/profile", response_model=AdminUserRead)
def update_profile(
    payload: AdminProfileUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AdminUserRead:
    if payload.username is not None:
        existing = (
            session.query(AdminUser)
            .filter(AdminUser.username == payload.username, AdminUser.id != admin.id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        admin.username = payload.username
    session.commit()
    session.refresh(admin)
    return AdminUserRead.model_validate(admin)


@router.get("/sessions", response_model=list[AdminSessionRead])
def list_sessions(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list:
    now = datetime.now(UTC)
    current_token = _extract_token(request)
    active = (
        session.query(AdminSession)
        .filter(AdminSession.admin_user_id == admin.id, AdminSession.expires_at > now)
        .order_by(AdminSession.created_at.desc())
        .all()
    )
    return [
        AdminSessionRead(
            id=s.id,
            created_at=s.created_at,
            expires_at=s.expires_at,
            is_current=(s.session_token == current_token),
        )
        for s in active
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: str,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    target = session.get(AdminSession, session_id)
    if target is None or target.admin_user_id != admin.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.delete(target)
    session.commit()
