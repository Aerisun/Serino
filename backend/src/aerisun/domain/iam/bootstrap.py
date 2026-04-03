from __future__ import annotations

import bcrypt
from sqlalchemy.orm import Session

from aerisun.domain.iam.models import AdminUser

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def hash_admin_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def add_admin_user(
    session: Session,
    *,
    username: str,
    password: str,
    is_active: bool = True,
) -> AdminUser:
    user = AdminUser(
        username=username,
        password_hash=hash_admin_password(password),
        is_active=is_active,
    )
    session.add(user)
    return user


def ensure_default_production_admin(
    session: Session,
    *,
    environment: str,
    is_first_boot: bool,
) -> AdminUser | None:
    if environment != "production" or not is_first_boot:
        return None
    if session.query(AdminUser).first() is not None:
        return None

    user = add_admin_user(
        session,
        username=DEFAULT_ADMIN_USERNAME,
        password=DEFAULT_ADMIN_PASSWORD,
    )
    session.commit()
    session.refresh(user)
    return user
