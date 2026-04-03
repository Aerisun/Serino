from __future__ import annotations

from datetime import datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from aerisun.domain.site_auth.models import (
    SiteAdminIdentity,
    SiteAuthConfig,
    SiteUser,
    SiteUserOAuthAccount,
    SiteUserSession,
)


def find_site_auth_config(session: Session) -> SiteAuthConfig | None:
    return session.scalars(select(SiteAuthConfig).order_by(SiteAuthConfig.created_at.asc())).first()


def create_site_auth_config(session: Session, **kwargs) -> SiteAuthConfig:
    config = SiteAuthConfig(**kwargs)
    session.add(config)
    return config


def find_user_by_email(session: Session, email: str) -> SiteUser | None:
    return session.scalars(select(SiteUser).where(SiteUser.email == email)).first()


def find_user_by_id(session: Session, user_id: str) -> SiteUser | None:
    return session.get(SiteUser, user_id)


def create_user(session: Session, **kwargs) -> SiteUser:
    user = SiteUser(**kwargs)
    session.add(user)
    return user


def find_session_by_token(session: Session, token: str) -> SiteUserSession | None:
    return session.scalars(select(SiteUserSession).where(SiteUserSession.session_token == token)).first()


def create_session(
    session: Session,
    *,
    site_user_id: str,
    token: str,
    expires_at: datetime,
    admin_verified_provider: str | None = None,
) -> SiteUserSession:
    site_session = SiteUserSession(
        site_user_id=site_user_id,
        session_token=token,
        expires_at=expires_at,
        admin_verified_provider=admin_verified_provider,
    )
    session.add(site_session)
    return site_session


def delete_session(session: Session, site_session: SiteUserSession) -> None:
    session.delete(site_session)


def delete_sessions_for_user(session: Session, site_user_id: str) -> int:
    sessions = session.scalars(select(SiteUserSession).where(SiteUserSession.site_user_id == site_user_id)).all()
    count = 0
    for item in sessions:
        session.delete(item)
        count += 1
    return count


def find_oauth_account(session: Session, *, provider: str, provider_subject: str) -> SiteUserOAuthAccount | None:
    return session.scalars(
        select(SiteUserOAuthAccount).where(
            SiteUserOAuthAccount.provider == provider,
            SiteUserOAuthAccount.provider_subject == provider_subject,
        )
    ).first()


def find_oauth_account_by_email(session: Session, *, provider: str, email: str) -> SiteUserOAuthAccount | None:
    return session.scalars(
        select(SiteUserOAuthAccount).where(
            SiteUserOAuthAccount.provider == provider,
            SiteUserOAuthAccount.provider_email == email,
        )
    ).first()


def create_oauth_account(session: Session, **kwargs) -> SiteUserOAuthAccount:
    account = SiteUserOAuthAccount(**kwargs)
    session.add(account)
    return account


def find_oauth_account_for_user(session: Session, *, site_user_id: str, provider: str) -> SiteUserOAuthAccount | None:
    return session.scalars(
        select(SiteUserOAuthAccount).where(
            SiteUserOAuthAccount.site_user_id == site_user_id,
            SiteUserOAuthAccount.provider == provider,
        )
    ).first()


def list_oauth_accounts_by_user_ids(session: Session, user_ids: list[str]) -> dict[str, list[SiteUserOAuthAccount]]:
    if not user_ids:
        return {}
    rows = list(
        session.scalars(
            select(SiteUserOAuthAccount)
            .where(SiteUserOAuthAccount.site_user_id.in_(user_ids))
            .order_by(SiteUserOAuthAccount.created_at.asc())
        ).all()
    )
    mapping: dict[str, list[SiteUserOAuthAccount]] = {}
    for row in rows:
        mapping.setdefault(row.site_user_id, []).append(row)
    return mapping


def list_site_users(
    session: Session,
    *,
    auth_mode: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SiteUser], int]:
    filters = []
    normalized_search = " ".join((search or "").strip().split())
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(or_(SiteUser.display_name.ilike(pattern), SiteUser.email.ilike(pattern)))

    oauth_exists = exists(select(SiteUserOAuthAccount.id).where(SiteUserOAuthAccount.site_user_id == SiteUser.id))
    if auth_mode == "email":
        filters.append(~oauth_exists)
    elif auth_mode == "binding":
        filters.append(oauth_exists)

    stmt = (
        select(SiteUser)
        .where(*filters)
        .order_by(
            SiteUser.last_login_at.is_(None),
            SiteUser.last_login_at.desc(),
            SiteUser.created_at.desc(),
        )
    )
    total = int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = list(session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return items, total


def find_user_by_identity_hint(session: Session, *, email: str, provider_email: str | None = None) -> SiteUser | None:
    filters = [SiteUser.email == email]
    if provider_email:
        filters.append(SiteUser.email == provider_email)
    return session.scalars(select(SiteUser).where(or_(*filters))).first()


def find_admin_identity_by_id(session: Session, identity_id: str) -> SiteAdminIdentity | None:
    return session.get(SiteAdminIdentity, identity_id)


def find_admin_identity_by_provider_identifier(
    session: Session,
    *,
    provider: str,
    identifier: str,
) -> SiteAdminIdentity | None:
    return session.scalars(
        select(SiteAdminIdentity).where(
            SiteAdminIdentity.provider == provider,
            SiteAdminIdentity.identifier == identifier,
        )
    ).first()


def find_admin_identity_for_user_provider(
    session: Session,
    *,
    site_user_id: str,
    provider: str,
) -> SiteAdminIdentity | None:
    return session.scalars(
        select(SiteAdminIdentity).where(
            SiteAdminIdentity.site_user_id == site_user_id,
            SiteAdminIdentity.provider == provider,
        )
    ).first()


def find_admin_identity_for_user(session: Session, *, site_user_id: str) -> SiteAdminIdentity | None:
    return session.scalars(
        select(SiteAdminIdentity)
        .where(SiteAdminIdentity.site_user_id == site_user_id)
        .order_by(SiteAdminIdentity.updated_at.desc(), SiteAdminIdentity.created_at.desc())
    ).first()


def find_admin_email_identity(session: Session, *, email: str) -> SiteAdminIdentity | None:
    normalized_email = email.strip().lower()
    return session.scalars(
        select(SiteAdminIdentity)
        .where(SiteAdminIdentity.provider == "email", SiteAdminIdentity.email == normalized_email)
        .order_by(SiteAdminIdentity.updated_at.desc(), SiteAdminIdentity.created_at.desc())
    ).first()


def create_admin_identity(session: Session, **kwargs) -> SiteAdminIdentity:
    identity = SiteAdminIdentity(**kwargs)
    session.add(identity)
    return identity


def delete_admin_identity(session: Session, identity: SiteAdminIdentity) -> None:
    session.delete(identity)


def list_admin_identities(session: Session) -> list[SiteAdminIdentity]:
    return list(
        session.scalars(
            select(SiteAdminIdentity).order_by(SiteAdminIdentity.updated_at.desc(), SiteAdminIdentity.created_at.desc())
        ).all()
    )


def list_admin_identities_by_user_ids(session: Session, user_ids: list[str]) -> dict[str, list[SiteAdminIdentity]]:
    if not user_ids:
        return {}
    rows = list(
        session.scalars(
            select(SiteAdminIdentity)
            .where(SiteAdminIdentity.site_user_id.in_(user_ids))
            .order_by(SiteAdminIdentity.updated_at.desc(), SiteAdminIdentity.created_at.desc())
        ).all()
    )
    mapping: dict[str, list[SiteAdminIdentity]] = {}
    for row in rows:
        mapping.setdefault(row.site_user_id, []).append(row)
    return mapping
