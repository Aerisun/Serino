from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.models import SiteAuthConfig
from aerisun.domain.site_auth.schemas import (
    OAuthProviderSecretStatusRead,
    OAuthProviderStatusRead,
    SiteAuthConfigAdminRead,
    SiteAuthConfigAdminUpdate,
)
from aerisun.domain.site_config import repository as site_config_repo

from .shared import (
    ALLOWED_ADMIN_AUTH_METHODS,
    ALLOWED_OAUTH_PROVIDERS,
    normalize_string_list,
)


def build_default_site_auth_config(session: Session) -> dict[str, object]:
    community_config = site_config_repo.find_community_config(session)
    default_providers = (
        list(community_config.oauth_providers)
        if community_config and community_config.oauth_providers
        else ["github", "google"]
    )
    visitor_oauth_providers = normalize_string_list(
        default_providers,
        ALLOWED_OAUTH_PROVIDERS,
    )
    return {
        "email_login_enabled": True,
        "visitor_oauth_providers": visitor_oauth_providers,
        "admin_auth_methods": ["google", "github"],
        "admin_email_enabled": False,
        # legacy fields retained in DB schema; values are no longer sourced from env by default
        "google_client_id": "",
        "google_client_secret": "",
        "github_client_id": "",
        "github_client_secret": "",
    }


def get_site_auth_config_orm(session: Session) -> SiteAuthConfig:
    config = repo.find_site_auth_config(session)
    if config is not None:
        return config
    config = repo.create_site_auth_config(session, **build_default_site_auth_config(session))
    session.commit()
    session.refresh(config)
    return config


def _provider_status(session: Session, provider: str) -> OAuthProviderStatusRead:
    settings = get_settings()
    config = get_site_auth_config_orm(session)

    enabled_for_visitors = provider in normalize_string_list(config.visitor_oauth_providers, ALLOWED_OAUTH_PROVIDERS)
    enabled_for_admin = provider in normalize_string_list(config.admin_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)

    client_id_secret, client_secret_secret = settings.oauth_provider_secrets(provider)

    def as_secret_status(secret) -> OAuthProviderSecretStatusRead:
        return OAuthProviderSecretStatusRead(
            configured=bool(secret.value),
            filename=secret.filename,
            source=secret.source,
        )

    ready = bool(client_id_secret.value and client_secret_secret.value)

    return OAuthProviderStatusRead(
        enabled_for_visitors=enabled_for_visitors,
        enabled_for_admin=enabled_for_admin,
        ready=ready,
        client_id=as_secret_status(client_id_secret),
        client_secret=as_secret_status(client_secret_secret),
    )


def get_site_auth_admin_config(session: Session) -> SiteAuthConfigAdminRead:
    config = get_site_auth_config_orm(session)
    return SiteAuthConfigAdminRead(
        id=config.id,
        email_login_enabled=bool(config.email_login_enabled),
        visitor_oauth_providers=list(config.visitor_oauth_providers or []),
        admin_auth_methods=list(config.admin_auth_methods or []),
        admin_email_enabled=bool(config.admin_email_enabled),
        google=_provider_status(session, "google"),
        github=_provider_status(session, "github"),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def update_site_auth_admin_config(session: Session, payload: SiteAuthConfigAdminUpdate) -> SiteAuthConfigAdminRead:
    config = get_site_auth_config_orm(session)
    updates = payload.model_dump(exclude_unset=True)
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
    return get_site_auth_admin_config(session)


def enabled_oauth_providers(session: Session) -> list[str]:
    config = get_site_auth_config_orm(session)
    visitor = normalize_string_list(config.visitor_oauth_providers, ALLOWED_OAUTH_PROVIDERS)
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
    client_id_secret, client_secret_secret = settings.oauth_provider_secrets(provider)
    return client_id_secret.value, client_secret_secret.value


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
