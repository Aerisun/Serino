from __future__ import annotations

import bcrypt
from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import AuthenticationFailed, ValidationError
from aerisun.domain.outbound_proxy.service import require_outbound_proxy_scope
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.models import SiteAuthConfig
from aerisun.domain.site_auth.schemas import SiteAuthConfigAdminRead, SiteAuthConfigAdminUpdate

from .shared import (
    ALLOWED_ADMIN_AUTH_METHODS,
    ALLOWED_OAUTH_PROVIDERS,
    normalize_string_list,
)


def build_default_site_auth_config(session: Session) -> dict[str, object]:
    settings = get_settings()
    return {
        "email_login_enabled": True,
        "visitor_oauth_providers": [],
        "admin_auth_methods": [],
        "admin_console_auth_methods": [],
        "admin_email_enabled": False,
        "admin_email_password_hash": None,
        "google_client_id": settings.oauth_google_client_id.strip(),
        "google_client_secret": settings.oauth_google_client_secret.strip(),
        "github_client_id": settings.oauth_github_client_id.strip(),
        "github_client_secret": settings.oauth_github_client_secret.strip(),
    }


def get_site_auth_config_orm(session: Session) -> SiteAuthConfig:
    config = repo.find_site_auth_config(session)
    if config is not None:
        return config
    config = repo.create_site_auth_config(session, **build_default_site_auth_config(session))
    session.commit()
    session.refresh(config)
    return config


def get_site_auth_admin_config(session: Session) -> SiteAuthConfigAdminRead:
    config = get_site_auth_config_orm(session)
    return SiteAuthConfigAdminRead(
        id=config.id,
        email_login_enabled=bool(config.email_login_enabled),
        visitor_oauth_providers=list(config.visitor_oauth_providers or []),
        admin_auth_methods=list(config.admin_auth_methods or []),
        admin_console_auth_methods=list(config.admin_console_auth_methods or []),
        admin_email_enabled=bool(config.admin_email_enabled),
        admin_email_password_set=bool((config.admin_email_password_hash or "").strip()),
        google_client_id=config.google_client_id,
        google_client_secret=config.google_client_secret,
        github_client_id=config.github_client_id,
        github_client_secret=config.github_client_secret,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def update_site_auth_admin_config(session: Session, payload: SiteAuthConfigAdminUpdate) -> SiteAuthConfigAdminRead:
    from aerisun.domain.automation.events import emit_site_auth_config_updated

    config = get_site_auth_config_orm(session)
    updates = payload.model_dump(exclude_unset=True)
    changed_fields = sorted(updates.keys())
    if "visitor_oauth_providers" in updates:
        updates["visitor_oauth_providers"] = normalize_string_list(
            updates["visitor_oauth_providers"],
            ALLOWED_OAUTH_PROVIDERS,
        )
    if "admin_auth_methods" in updates:
        updates["admin_auth_methods"] = normalize_string_list(
            updates["admin_auth_methods"],
            ALLOWED_ADMIN_AUTH_METHODS,
        )
    if "admin_console_auth_methods" in updates:
        updates["admin_console_auth_methods"] = normalize_string_list(
            updates["admin_console_auth_methods"],
            ALLOWED_ADMIN_AUTH_METHODS,
        )
    requires_oauth_proxy = ("visitor_oauth_providers" in updates and bool(updates["visitor_oauth_providers"])) or (
        "admin_auth_methods" in updates
        and any(item in ALLOWED_OAUTH_PROVIDERS for item in updates["admin_auth_methods"])
    )
    if requires_oauth_proxy:
        require_outbound_proxy_scope(session, scope="oauth")
    next_admin_email_password = updates.pop("admin_email_password", None) if "admin_email_password" in updates else None
    for key, value in updates.items():
        setattr(config, key, value)
    if next_admin_email_password is not None:
        normalized_password = next_admin_email_password.strip()
        if len(normalized_password) < 8:
            raise ValidationError("管理员邮箱密码至少需要 8 个字符。")
        config.admin_email_password_hash = bcrypt.hashpw(
            normalized_password.encode(),
            bcrypt.gensalt(),
        ).decode()
    session.commit()
    session.refresh(config)
    emit_site_auth_config_updated(
        session,
        changed_fields=changed_fields,
        visitor_oauth_providers=list(config.visitor_oauth_providers or []),
        admin_auth_methods=list(config.admin_auth_methods or []),
        admin_console_auth_methods=list(config.admin_console_auth_methods or []),
        email_login_enabled=bool(config.email_login_enabled),
        admin_email_enabled=bool(config.admin_email_enabled),
    )
    return get_site_auth_admin_config(session)


def enabled_visitor_oauth_providers(session: Session) -> list[str]:
    config = get_site_auth_config_orm(session)
    return normalize_string_list(config.visitor_oauth_providers, ALLOWED_OAUTH_PROVIDERS)


def enabled_oauth_providers(session: Session) -> list[str]:
    config = get_site_auth_config_orm(session)
    visitor = enabled_visitor_oauth_providers(session)
    admin = [
        item
        for item in normalize_string_list(config.admin_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)
        if item in ALLOWED_OAUTH_PROVIDERS
    ]
    return normalize_string_list([*visitor, *admin], ALLOWED_OAUTH_PROVIDERS)


def email_login_enabled(session: Session) -> bool:
    config = get_site_auth_config_orm(session)
    return bool(config.email_login_enabled or config.admin_email_enabled)


def oauth_credentials(session: Session, provider: str) -> tuple[str, str]:
    settings = get_settings()
    config = get_site_auth_config_orm(session)
    if provider == "google":
        return (
            config.google_client_id.strip() or settings.oauth_google_client_id.strip(),
            config.google_client_secret.strip() or settings.oauth_google_client_secret.strip(),
        )
    if provider == "github":
        return (
            config.github_client_id.strip() or settings.oauth_github_client_id.strip(),
            config.github_client_secret.strip() or settings.oauth_github_client_secret.strip(),
        )
    return "", ""


def get_admin_login_options(session: Session) -> dict[str, object]:
    config = get_site_auth_config_orm(session)
    oauth_providers = [
        provider
        for provider in normalize_string_list(config.admin_console_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)
        if provider in ALLOWED_OAUTH_PROVIDERS
    ]
    return {
        "oauth_providers": oauth_providers,
        "email_enabled": bool(
            config.admin_email_enabled
            and (config.admin_email_password_hash or "").strip()
            and "email" in normalize_string_list(config.admin_console_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)
        ),
    }


def enabled_admin_console_auth_methods(session: Session) -> list[str]:
    config = get_site_auth_config_orm(session)
    return normalize_string_list(config.admin_console_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)


def admin_console_auth_method_enabled(session: Session, provider: str | None) -> bool:
    normalized_provider = str(provider or "").strip().lower()
    if not normalized_provider:
        return False
    return normalized_provider in enabled_admin_console_auth_methods(session)


def validate_admin_email_password(session: Session, password: str) -> None:
    config = get_site_auth_config_orm(session)
    stored_password_hash = (config.admin_email_password_hash or "").strip()
    if not stored_password_hash:
        raise ValidationError("管理员邮箱密码尚未设置。")
    if not bcrypt.checkpw(password.encode(), stored_password_hash.encode()):
        raise AuthenticationFailed("管理员邮箱密码错误。")
