from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.iam import repository as repo
from aerisun.domain.iam.models import AdminUser, ApiKey
from aerisun.domain.iam.schemas import (
    AdminSessionRead,
    AdminUserRead,
    ApiKeyAdminRead,
    ApiKeyCreateResponse,
    ApiKeyUpdate,
    LoginResponse,
)

SESSION_TTL_HOURS = 24


def authenticate_admin(session: Session, username: str, password: str) -> AdminUser:
    """Verify credentials and return the admin user. Raises LookupError or PermissionError."""
    user = repo.find_admin_by_username(session, username)
    if user is None or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise LookupError("Invalid username or password")
    if not user.is_active:
        raise PermissionError("Account is disabled")
    return user


def create_admin_session(session: Session, admin_user_id: str, ttl_hours: int | None = None) -> LoginResponse:
    """Create a new session token for the given admin user."""
    settings = get_settings()
    ttl = ttl_hours or getattr(settings, "session_ttl_hours", SESSION_TTL_HOURS)
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(UTC) + timedelta(hours=ttl)
    repo.create_session(session, admin_user_id=admin_user_id, token=token, expires_at=expires_at)
    session.commit()
    return LoginResponse(token=token, expires_at=expires_at)


def destroy_admin_sessions(session: Session, admin_user_id: str) -> None:
    """Delete all sessions for the given admin user."""
    repo.delete_sessions_for_user(session, admin_user_id)
    session.commit()


def change_admin_password(session: Session, admin: AdminUser, current_password: str, new_password: str) -> None:
    """Verify old password and update to new. Raises ValueError on mismatch."""
    if not bcrypt.checkpw(current_password.encode(), admin.password_hash.encode()):
        raise ValueError("Current password is incorrect")
    admin.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    session.commit()


def update_admin_profile(session: Session, admin: AdminUser, username: str | None = None) -> AdminUserRead:
    """Update admin profile. Raises ValueError on username conflict."""
    if username is not None:
        existing = repo.find_admin_by_username_excluding(session, username, admin.id)
        if existing:
            raise ValueError("Username already taken")
        admin.username = username
    session.commit()
    session.refresh(admin)
    return AdminUserRead.model_validate(admin)


def list_admin_sessions(
    session: Session, admin_user_id: str, current_token: str | None = None
) -> list[AdminSessionRead]:
    """List active (not expired) sessions for the given admin user."""
    now = datetime.now(UTC)
    active = repo.find_active_sessions(session, admin_user_id, now=now)
    return [
        AdminSessionRead(
            id=s.id,
            created_at=s.created_at,
            expires_at=s.expires_at,
            is_current=(s.session_token == current_token),
        )
        for s in active
    ]


def revoke_admin_session(session: Session, admin_user_id: str, session_id: str) -> None:
    """Revoke a specific session. Raises LookupError if not found or not owned."""
    target = repo.find_session_by_id(session, session_id)
    if target is None or target.admin_user_id != admin_user_id:
        raise LookupError("Session not found")
    session.delete(target)
    session.commit()


def validate_session_token(session: Session, token: str) -> AdminUser:
    """Validate a session token and return the admin user. Raises PermissionError."""
    admin_session = repo.find_session_by_token(session, token)
    if admin_session is None:
        raise PermissionError("Invalid or expired session token")
    now_utc = datetime.now(UTC)
    now = now_utc.replace(tzinfo=None) if admin_session.expires_at.tzinfo is None else now_utc
    if admin_session.expires_at < now:
        session.delete(admin_session)
        session.commit()
        raise PermissionError("Session expired")
    user = session.get(AdminUser, admin_session.admin_user_id)
    if user is None or not user.is_active:
        raise PermissionError("User not found or inactive")
    return user


def validate_api_key(session: Session, token: str, required_scopes: tuple[str, ...]) -> ApiKey:
    """Validate an API key and check scopes. Raises PermissionError."""
    prefix = token[:8]
    key = repo.find_api_key_by_prefix(session, prefix)
    if key is None:
        raise PermissionError("Invalid API key")
    if not bcrypt.checkpw(token.encode(), key.hashed_secret.encode()):
        raise PermissionError("Invalid API key")
    missing = [s for s in required_scopes if s not in key.scopes]
    if missing:
        raise PermissionError(f"Missing required scopes: {', '.join(missing)}")
    key.last_used_at = datetime.now(UTC)
    session.commit()
    return key


# ---------------------------------------------------------------------------
# API Key CRUD
# ---------------------------------------------------------------------------


def list_api_keys(session: Session) -> list[ApiKeyAdminRead]:
    keys = repo.find_all_api_keys(session)
    return [ApiKeyAdminRead.model_validate(k) for k in keys]


def create_api_key(session: Session, key_name: str, scopes: list[str]) -> ApiKeyCreateResponse:
    raw_secret = secrets.token_urlsafe(48)
    prefix = raw_secret[:8]
    hashed = bcrypt.hashpw(raw_secret.encode(), bcrypt.gensalt()).decode()
    key = repo.create_api_key(
        session,
        key_name=key_name,
        key_prefix=prefix,
        hashed_secret=hashed,
        scopes=scopes,
    )
    session.commit()
    session.refresh(key)
    return ApiKeyCreateResponse(
        item=ApiKeyAdminRead.model_validate(key),
        raw_key=raw_secret,
    )


def update_api_key(session: Session, key_id: str, payload: ApiKeyUpdate) -> ApiKeyAdminRead:
    key = repo.find_api_key_by_id(session, key_id)
    if key is None:
        raise LookupError("API key not found")
    repo.update_api_key(session, key, payload.model_dump(exclude_unset=True))
    session.commit()
    session.refresh(key)
    return ApiKeyAdminRead.model_validate(key)


def delete_api_key(session: Session, key_id: str) -> None:
    key = repo.find_api_key_by_id(session, key_id)
    if key is None:
        raise LookupError("API key not found")
    repo.delete_api_key(session, key)
    session.commit()
