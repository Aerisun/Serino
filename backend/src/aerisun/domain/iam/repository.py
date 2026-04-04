from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from aerisun.domain.iam.models import AdminSession, AdminUser, ApiKey


def find_admin_by_username(session: Session, username: str) -> AdminUser | None:
    """Find admin user by username."""
    return session.query(AdminUser).filter(AdminUser.username == username).first()


def find_admin_by_username_excluding(session: Session, username: str, exclude_id: str) -> AdminUser | None:
    """Find admin user by username, excluding a specific user id (for uniqueness checks)."""
    return session.query(AdminUser).filter(AdminUser.username == username, AdminUser.id != exclude_id).first()


def create_session(session: Session, *, admin_user_id: str, token: str, expires_at: datetime) -> AdminSession:
    """Create a new admin session. Caller must commit."""
    admin_session = AdminSession(
        admin_user_id=admin_user_id,
        session_token=token,
        expires_at=expires_at,
    )
    session.add(admin_session)
    return admin_session


def delete_sessions_for_user(session: Session, admin_user_id: str) -> int:
    """Delete all sessions for a user. Caller must commit. Returns count deleted."""
    sessions = session.query(AdminSession).filter(AdminSession.admin_user_id == admin_user_id).all()
    count = len(sessions)
    for s in sessions:
        session.delete(s)
    return count


def find_active_sessions(session: Session, admin_user_id: str, *, now: datetime) -> list[AdminSession]:
    """Find all non-expired sessions for a user, ordered by created_at desc."""
    return list(
        session.query(AdminSession)
        .filter(
            AdminSession.admin_user_id == admin_user_id,
            AdminSession.expires_at > now,
        )
        .order_by(AdminSession.created_at.desc())
        .all()
    )


def find_session_by_id(session: Session, session_id: str) -> AdminSession | None:
    """Find a session by its primary key."""
    return session.get(AdminSession, session_id)


def delete_session(session: Session, admin_session: AdminSession) -> None:
    """Delete a specific session. Caller must commit."""
    session.delete(admin_session)


# -- API Keys --


def find_all_api_keys(session: Session) -> list[ApiKey]:
    """List all API keys ordered by created_at desc."""
    return list(session.query(ApiKey).order_by(ApiKey.created_at.desc()).all())


def create_api_key(session: Session, **kwargs) -> ApiKey:
    """Create a new API key. Caller must commit."""
    key = ApiKey(**kwargs)
    session.add(key)
    return key


def find_api_key_by_id(session: Session, key_id: str) -> ApiKey | None:
    """Find an API key by its primary key."""
    return session.get(ApiKey, key_id)


def update_api_key(session: Session, key: ApiKey, data: dict) -> ApiKey:
    """Apply partial update to an API key. Caller must commit."""
    for k, v in data.items():
        setattr(key, k, v)
    return key


def delete_api_key(session: Session, key: ApiKey) -> None:
    """Delete an API key. Caller must commit."""
    session.delete(key)


def find_session_by_token(session: Session, token: str) -> AdminSession | None:
    """Find a session by its token."""
    return session.query(AdminSession).filter(AdminSession.session_token == token).first()


def find_api_key_by_prefix(session: Session, prefix: str) -> ApiKey | None:
    """Find an API key by its prefix."""
    return session.query(ApiKey).filter(ApiKey.key_prefix == prefix).first()


def find_api_key_by_prefix_and_suffix(session: Session, prefix: str, suffix: str) -> ApiKey | None:
    """Find an API key by exact prefix and suffix hints."""

    return (
        session.query(ApiKey)
        .filter(
            ApiKey.key_prefix == prefix,
            ApiKey.key_suffix == suffix,
        )
        .first()
    )
