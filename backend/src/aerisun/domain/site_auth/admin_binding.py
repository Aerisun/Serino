from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.exceptions import AuthenticationFailed, ValidationError
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.schemas import SiteAdminEmailIdentityBindRequest, SiteAdminIdentityAdminRead

from .config_service import (
    admin_console_auth_method_enabled,
    get_site_auth_config_orm,
)
from .config_service import (
    get_admin_login_options as _get_admin_login_options,
)
from .profile import build_avatar_candidates, suggest_display_name
from .shared import ALLOWED_ADMIN_AUTH_METHODS, normalize_email, normalize_string_list


def list_site_admin_identities_admin(session: Session) -> list[SiteAdminIdentityAdminRead]:
    identities = repo.list_admin_identities(session)
    users = {
        user.id: user
        for user in [repo.find_user_by_id(session, identity.site_user_id) for identity in identities]
        if user is not None
    }
    items: list[SiteAdminIdentityAdminRead] = []
    for identity in identities:
        user = users.get(identity.site_user_id)
        if user is None:
            continue
        items.append(
            SiteAdminIdentityAdminRead(
                id=identity.id,
                site_user_id=identity.site_user_id,
                provider=identity.provider,
                identifier=identity.identifier,
                email=identity.email,
                site_user_display_name=user.display_name,
                site_user_avatar_url=user.avatar_url,
                provider_display_name=identity.provider_display_name,
                created_at=identity.created_at,
                updated_at=identity.updated_at,
            )
        )
    return items


def upsert_admin_identity(
    session: Session,
    *,
    site_user: SiteUser,
    admin_user_id: str,
    provider: str,
    identifier: str,
    email: str,
    provider_display_name: str | None = None,
) -> SiteAdminIdentityAdminRead:
    from aerisun.domain.automation.events import emit_site_admin_identity_created

    normalized_provider = provider.strip().lower()
    normalized_identifier = " ".join((identifier or "").strip().split())
    normalized_email = normalize_email(email)
    if normalized_provider not in ALLOWED_ADMIN_AUTH_METHODS:
        raise ValidationError("不支持的管理员认证方式。")
    if not normalized_identifier:
        raise ValidationError("管理员绑定缺少有效标识。")
    if not normalized_email:
        raise ValidationError("管理员绑定缺少有效邮箱。")

    identity = repo.find_admin_identity_by_provider_identifier(
        session,
        provider=normalized_provider,
        identifier=normalized_identifier,
    )
    if identity is None:
        identity = repo.find_admin_identity_for_user_provider(
            session,
            site_user_id=site_user.id,
            provider=normalized_provider,
        )
    created = identity is None
    if identity is None:
        identity = repo.create_admin_identity(
            session,
            site_user_id=site_user.id,
            admin_user_id=admin_user_id,
            provider=normalized_provider,
            identifier=normalized_identifier,
            email=normalized_email,
            provider_display_name=provider_display_name,
        )
    else:
        identity.site_user_id = site_user.id
        identity.admin_user_id = admin_user_id
        identity.identifier = normalized_identifier
        identity.email = normalized_email
        identity.provider_display_name = provider_display_name

    session.commit()
    session.refresh(identity)
    if created:
        emit_site_admin_identity_created(
            session,
            identity_id=identity.id,
            site_user_id=identity.site_user_id,
            provider=identity.provider,
            email=identity.email,
        )
    user = repo.find_user_by_id(session, identity.site_user_id)
    if user is None:
        raise ValidationError("管理员绑定的站点用户不存在。")
    return SiteAdminIdentityAdminRead(
        id=identity.id,
        site_user_id=identity.site_user_id,
        provider=identity.provider,
        identifier=identity.identifier,
        email=identity.email,
        site_user_display_name=user.display_name,
        site_user_avatar_url=user.avatar_url,
        provider_display_name=identity.provider_display_name,
        created_at=identity.created_at,
        updated_at=identity.updated_at,
    )


def bind_site_admin_identity_by_email(
    session: Session,
    payload: SiteAdminEmailIdentityBindRequest,
    *,
    admin_user_id: str,
) -> SiteAdminIdentityAdminRead:
    config = get_site_auth_config_orm(session)
    if not config.admin_email_enabled:
        raise ValidationError("当前未启用管理员邮箱身份。")

    normalized_email = normalize_email(payload.email)
    if not normalized_email or "@" not in normalized_email:
        raise ValidationError("请输入有效邮箱。")

    user = repo.find_user_by_email(session, normalized_email)
    if user is None:
        user = repo.create_user(
            session,
            email=normalized_email,
            display_name=suggest_display_name(normalized_email),
            avatar_url=build_avatar_candidates(normalized_email, 1)[0].avatar_url,
            primary_auth_provider="email",
            last_login_at=None,
        )
        session.flush()

    return upsert_admin_identity(
        session,
        site_user=user,
        admin_user_id=admin_user_id,
        provider="email",
        identifier=normalized_email,
        email=normalized_email,
        provider_display_name=user.display_name,
    )


def bind_site_admin_identity_from_current_user(
    session: Session,
    current_user: SiteUser,
    *,
    provider: str,
    admin_user_id: str,
) -> SiteAdminIdentityAdminRead:
    config = get_site_auth_config_orm(session)
    normalized_provider = provider.strip().lower()
    if normalized_provider == "email":
        if not config.admin_email_enabled:
            raise ValidationError("当前未启用管理员邮箱身份。")
        return upsert_admin_identity(
            session,
            site_user=current_user,
            admin_user_id=admin_user_id,
            provider="email",
            identifier=current_user.email,
            email=current_user.email,
            provider_display_name=current_user.display_name,
        )

    if normalized_provider not in normalize_string_list(config.admin_auth_methods, ALLOWED_ADMIN_AUTH_METHODS):
        raise ValidationError("当前未启用该管理员认证方式。")

    oauth_account = repo.find_oauth_account_for_user(
        session,
        site_user_id=current_user.id,
        provider=normalized_provider,
    )
    if oauth_account is None:
        raise ValidationError("请先用该方式完成一次前台登录，再回来绑定管理员身份。")

    return upsert_admin_identity(
        session,
        site_user=current_user,
        admin_user_id=admin_user_id,
        provider=normalized_provider,
        identifier=oauth_account.provider_subject,
        email=oauth_account.provider_email or current_user.email,
        provider_display_name=oauth_account.provider_display_name or current_user.display_name,
    )


def delete_site_admin_identity(session: Session, identity_id: str) -> None:
    from aerisun.domain.automation.events import emit_site_admin_identity_deleted

    identity = repo.find_admin_identity_by_id(session, identity_id)
    if identity is None:
        raise ValidationError("管理员身份不存在。")
    snapshot = {
        "identity_id": identity.id,
        "site_user_id": identity.site_user_id,
        "provider": identity.provider,
        "email": identity.email,
    }
    repo.delete_admin_identity(session, identity)
    session.commit()
    emit_site_admin_identity_deleted(session, **snapshot)


def get_admin_login_options(session: Session) -> dict[str, object]:
    return _get_admin_login_options(session)


def resolve_admin_user_id_for_site_session(
    session: Session,
    current_user: SiteUser,
    current_site_session: SiteUserSession,
) -> str:
    verified_provider = (current_site_session.admin_verified_provider or "").strip().lower()
    if not verified_provider:
        raise AuthenticationFailed("当前站点会话还没有完成管理员验证。")
    if not admin_console_auth_method_enabled(session, verified_provider):
        raise AuthenticationFailed("当前管理员身份未开启进入管理台。")
    identity = repo.find_admin_identity_for_user_provider(
        session,
        site_user_id=current_user.id,
        provider=verified_provider,
    )
    if identity is None or not identity.admin_user_id:
        raise AuthenticationFailed("当前站点身份没有绑定后台管理员权限。")
    return identity.admin_user_id


def resolve_admin_user_id_for_email(session: Session, email: str) -> str:
    normalized_email = normalize_email(email)
    if not normalized_email or "@" not in normalized_email:
        raise ValidationError("请输入有效邮箱。")
    config = get_site_auth_config_orm(session)
    if not config.admin_email_enabled:
        raise ValidationError("当前未启用管理员邮箱登录。")
    if not admin_console_auth_method_enabled(session, "email"):
        raise ValidationError("当前未启用管理员邮箱登录。")
    identity = repo.find_admin_email_identity(session, email=normalized_email)
    if identity is None or not identity.admin_user_id:
        raise AuthenticationFailed("这个邮箱没有绑定后台管理员权限。")
    return identity.admin_user_id
