from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
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
    visitor_oauth_providers = normalize_string_list(
        ["github", "google"],
        ALLOWED_OAUTH_PROVIDERS,
    )
    return {
        "email_login_enabled": True,
        "visitor_oauth_providers": visitor_oauth_providers,
        "admin_auth_methods": ["google", "github"],
        "admin_email_enabled": False,
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
    return SiteAuthConfigAdminRead.model_validate(get_site_auth_config_orm(session))


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
    for key, value in updates.items():
        setattr(config, key, value)
    session.commit()
    session.refresh(config)
    emit_site_auth_config_updated(
        session,
        changed_fields=changed_fields,
        visitor_oauth_providers=list(config.visitor_oauth_providers or []),
        admin_auth_methods=list(config.admin_auth_methods or []),
        email_login_enabled=bool(config.email_login_enabled),
        admin_email_enabled=bool(config.admin_email_enabled),
    )
    return SiteAuthConfigAdminRead.model_validate(config)


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
        for provider in normalize_string_list(config.admin_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)
        if provider in ALLOWED_OAUTH_PROVIDERS
    ]
    return {
        "oauth_providers": oauth_providers,
        "email_enabled": bool(config.admin_email_enabled),
    }
