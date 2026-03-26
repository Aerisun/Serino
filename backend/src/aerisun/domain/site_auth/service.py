from __future__ import annotations

import base64
import json
import secrets
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.models import SiteAuthConfig, SiteUser
from aerisun.domain.site_auth.schemas import (
    EmailLoginRequest,
    EmailLoginResponse,
    OAuthProviderCallbackResult,
    SiteAdminEmailIdentityBindRequest,
    SiteAdminIdentityAdminRead,
    SiteAuthAvatarCandidate,
    SiteAuthAvatarCandidateBatchRead,
    SiteAuthConfigAdminRead,
    SiteAuthConfigAdminUpdate,
    SiteAuthProfileUpdateRequest,
    SiteAuthStateRead,
    SiteAuthUserRead,
    SiteUserAdminRead,
    SiteUserOAuthAccountAdminRead,
)
from aerisun.domain.site_config import repository as site_config_repo
from aerisun.domain.waline.service import sync_site_user_comment_profile

SESSION_TTL_HOURS = 24 * 30
AVATAR_PICKER_COUNT = 12
AVATAR_POOL_SIZE = 1000
DICEBEAR_NOTIONISTS_BASE_URL = "https://api.dicebear.com/9.x/notionists/svg"
ALLOWED_OAUTH_PROVIDERS = {"google", "github"}
ALLOWED_ADMIN_AUTH_METHODS = {"email", "google", "github"}
ADMIN_COMMENT_AVATAR_KEY = "site-admin"


@dataclass(slots=True)
class OAuthStatePayload:
    provider: str
    state: str
    return_to: str


@dataclass(slots=True)
class ResolvedAdminIdentity:
    is_admin: bool
    effective_display_name: str
    effective_avatar_url: str


def _normalize_email(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_display_name(value: str | None) -> str:
    normalized = " ".join((value or "").strip().split())
    return normalized


def _normalize_return_to(value: str | None) -> str:
    candidate = (value or "/").strip() or "/"
    if not candidate.startswith("/"):
        return "/"
    return candidate


def _avatar_hash(value: str) -> int:
    hash_value = 0x811C9DC5
    for character in value:
        hash_value ^= ord(character)
        hash_value = (hash_value * 0x01000193) & 0xFFFFFFFF
    return hash_value


def _seeded_random(seed_value: str) -> int:
    return _avatar_hash(seed_value) or 1


def _next_seeded_random(state: int) -> tuple[int, float]:
    next_state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
    return next_state, next_state / 0x100000000


def _sample_avatar_indexes(identity: str) -> list[int]:
    normalized_identity = _normalize_email(identity) or "visitor"
    pool = list(range(AVATAR_POOL_SIZE))
    state = _seeded_random(normalized_identity)

    for index in range(len(pool) - 1, 0, -1):
        state, random_value = _next_seeded_random(state)
        target = int(random_value * (index + 1))
        pool[index], pool[target] = pool[target], pool[index]

    return pool


def _resolve_avatar_batch(identity: str, batch: int, count: int = AVATAR_PICKER_COUNT) -> tuple[list[int], int, int]:
    if count <= 0:
        return [], 0, 1

    pool = _sample_avatar_indexes(identity)
    total_batches = max((len(pool) + count - 1) // count, 1)
    normalized_batch = batch % total_batches
    start = normalized_batch * count
    end = start + count
    return pool[start:end], normalized_batch, total_batches


def _avatar_seed(identity: str, index: int) -> str:
    return f"{_avatar_hash(f'{identity}:{index}'):08x}"


def _avatar_url_for_seed(seed: str) -> str:
    return f"{DICEBEAR_NOTIONISTS_BASE_URL}?seed={seed}"


def build_avatar_candidates(
    identity: str,
    count: int = AVATAR_PICKER_COUNT,
    batch: int = 0,
) -> list[SiteAuthAvatarCandidate]:
    normalized_identity = _normalize_email(identity) or "visitor"
    candidates: list[SiteAuthAvatarCandidate] = []
    indexes, _, _ = _resolve_avatar_batch(normalized_identity, batch, count)
    for pool_index in indexes:
        seed = _avatar_seed(normalized_identity, pool_index)
        candidates.append(
            SiteAuthAvatarCandidate(
                key=seed,
                label=f"Notionists {pool_index:03d}",
                avatar_url=_avatar_url_for_seed(seed),
            )
        )
    return candidates


def build_avatar_candidate_batch(
    identity: str,
    *,
    batch: int = 0,
    count: int = AVATAR_PICKER_COUNT,
) -> SiteAuthAvatarCandidateBatchRead:
    normalized_identity = _normalize_email(identity)
    if not normalized_identity or "@" not in normalized_identity:
        raise ValidationError("请输入有效邮箱。")

    indexes, normalized_batch, total_batches = _resolve_avatar_batch(normalized_identity, batch, count)
    candidates: list[SiteAuthAvatarCandidate] = []
    for pool_index in indexes:
        seed = _avatar_seed(normalized_identity, pool_index)
        candidates.append(
            SiteAuthAvatarCandidate(
                key=seed,
                label=f"Notionists {pool_index:03d}",
                avatar_url=_avatar_url_for_seed(seed),
            )
        )

    return SiteAuthAvatarCandidateBatchRead(
        batch=normalized_batch,
        total_batches=total_batches,
        avatar_candidates=candidates,
    )


def suggest_display_name(email: str) -> str:
    local_part = _normalize_email(email).split("@", 1)[0]
    base = local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return _normalize_display_name(base.title() or "Visitor") or "Visitor"


def _resolve_admin_display_name(session: Session) -> str:
    site = site_config_repo.find_site_profile(session)
    title = _normalize_display_name(site.title if site else "")
    if title:
        return title
    fallback = _normalize_display_name(site.name if site else "")
    return fallback or "管理员"


def _resolve_admin_avatar_url(session: Session) -> str:
    site = site_config_repo.find_site_profile(session)
    for candidate in (
        site.hero_image_url if site else "",
        site.hero_poster_url if site else "",
        site.og_image if site else "",
    ):
        resolved = str(candidate or "").strip()
        if resolved:
            return resolved
    seed = _avatar_seed(_resolve_admin_display_name(session).lower(), 0)
    return _avatar_url_for_seed(seed)


def _resolve_admin_identity(session: Session, user: SiteUser) -> ResolvedAdminIdentity:
    admin_bindings = repo.list_admin_identities_by_user_ids(session, [user.id]).get(user.id, [])
    if not admin_bindings:
        return ResolvedAdminIdentity(
            is_admin=False,
            effective_display_name=user.display_name,
            effective_avatar_url=user.avatar_url,
        )
    return ResolvedAdminIdentity(
        is_admin=True,
        effective_display_name=_resolve_admin_display_name(session),
        effective_avatar_url=_resolve_admin_avatar_url(session),
    )


def _user_to_read(session: Session, user: SiteUser) -> SiteAuthUserRead:
    admin_identity = _resolve_admin_identity(session, user)
    return SiteAuthUserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        effective_display_name=admin_identity.effective_display_name,
        effective_avatar_url=admin_identity.effective_avatar_url,
        primary_auth_provider=user.primary_auth_provider,
        is_admin=admin_identity.is_admin,
        last_login_at=user.last_login_at,
    )


def _normalize_string_list(values: list[str] | None, allowed: set[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in values or []:
        item = str(raw or "").strip().lower()
        if not item or item not in allowed or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def build_default_site_auth_config(session: Session) -> dict[str, object]:
    settings = get_settings()
    community_config = site_config_repo.find_community_config(session)
    default_providers = (
        list(community_config.oauth_providers)
        if community_config and community_config.oauth_providers
        else ["github", "google"]
    )
    visitor_oauth_providers = _normalize_string_list(
        default_providers,
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


def _get_site_auth_config_orm(session: Session) -> SiteAuthConfig:
    config = repo.find_site_auth_config(session)
    if config is not None:
        return config
    config = repo.create_site_auth_config(session, **build_default_site_auth_config(session))
    session.commit()
    session.refresh(config)
    return config


def get_site_auth_admin_config(session: Session) -> SiteAuthConfigAdminRead:
    return SiteAuthConfigAdminRead.model_validate(_get_site_auth_config_orm(session))


def update_site_auth_admin_config(session: Session, payload: SiteAuthConfigAdminUpdate) -> SiteAuthConfigAdminRead:
    config = _get_site_auth_config_orm(session)
    updates = payload.model_dump(exclude_unset=True)
    if "visitor_oauth_providers" in updates:
        updates["visitor_oauth_providers"] = _normalize_string_list(
            updates["visitor_oauth_providers"],
            ALLOWED_OAUTH_PROVIDERS,
        )
    if "admin_auth_methods" in updates:
        updates["admin_auth_methods"] = _normalize_string_list(
            updates["admin_auth_methods"],
            ALLOWED_ADMIN_AUTH_METHODS,
        )
    for key, value in updates.items():
        setattr(config, key, value)
    session.commit()
    session.refresh(config)
    return SiteAuthConfigAdminRead.model_validate(config)


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


def _upsert_admin_identity(
    session: Session,
    *,
    site_user: SiteUser,
    admin_user_id: str,
    provider: str,
    identifier: str,
    email: str,
    provider_display_name: str | None = None,
) -> SiteAdminIdentityAdminRead:
    normalized_provider = provider.strip().lower()
    normalized_identifier = " ".join((identifier or "").strip().split())
    normalized_email = _normalize_email(email)
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
    config = _get_site_auth_config_orm(session)
    if not config.admin_email_enabled:
        raise ValidationError("当前未启用管理员邮箱身份。")

    normalized_email = _normalize_email(payload.email)
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

    return _upsert_admin_identity(
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
    config = _get_site_auth_config_orm(session)
    normalized_provider = provider.strip().lower()
    if normalized_provider == "email":
        if not config.admin_email_enabled:
            raise ValidationError("当前未启用管理员邮箱身份。")
        return _upsert_admin_identity(
            session,
            site_user=current_user,
            admin_user_id=admin_user_id,
            provider="email",
            identifier=current_user.email,
            email=current_user.email,
            provider_display_name=current_user.display_name,
        )

    if normalized_provider not in _normalize_string_list(config.admin_auth_methods, ALLOWED_ADMIN_AUTH_METHODS):
        raise ValidationError("当前未启用该管理员认证方式。")

    oauth_account = repo.find_oauth_account_for_user(
        session,
        site_user_id=current_user.id,
        provider=normalized_provider,
    )
    if oauth_account is None:
        raise ValidationError("请先用该方式完成一次前台登录，再回来绑定管理员身份。")

    return _upsert_admin_identity(
        session,
        site_user=current_user,
        admin_user_id=admin_user_id,
        provider=normalized_provider,
        identifier=oauth_account.provider_subject,
        email=oauth_account.provider_email or current_user.email,
        provider_display_name=oauth_account.provider_display_name or current_user.display_name,
    )


def delete_site_admin_identity(session: Session, identity_id: str) -> None:
    identity = repo.find_admin_identity_by_id(session, identity_id)
    if identity is None:
        raise ValidationError("管理员身份不存在。")
    repo.delete_admin_identity(session, identity)
    session.commit()


def get_admin_login_options(session: Session) -> dict[str, object]:
    config = _get_site_auth_config_orm(session)
    oauth_providers = [
        provider
        for provider in _normalize_string_list(config.admin_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)
        if provider in ALLOWED_OAUTH_PROVIDERS
    ]
    return {
        "oauth_providers": oauth_providers,
        "email_enabled": bool(config.admin_email_enabled),
    }


def resolve_admin_user_id_for_site_user(session: Session, current_user: SiteUser) -> str:
    identity = repo.find_admin_identity_for_user(session, site_user_id=current_user.id)
    if identity is None or not identity.admin_user_id:
        raise AuthenticationFailed("当前站点身份没有绑定后台管理员权限。")
    return identity.admin_user_id


def resolve_admin_user_id_for_email(session: Session, email: str) -> str:
    normalized_email = _normalize_email(email)
    if not normalized_email or "@" not in normalized_email:
        raise ValidationError("请输入有效邮箱。")
    config = _get_site_auth_config_orm(session)
    if not config.admin_email_enabled:
        raise ValidationError("当前未启用管理员邮箱登录。")
    identity = repo.find_admin_email_identity(session, email=normalized_email)
    if identity is None or not identity.admin_user_id:
        raise AuthenticationFailed("这个邮箱没有绑定后台管理员权限。")
    return identity.admin_user_id


def list_site_users_admin(
    session: Session,
    *,
    auth_mode: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SiteUserAdminRead], int]:
    users, total = repo.list_site_users(
        session,
        auth_mode=auth_mode,
        search=search,
        page=page,
        page_size=page_size,
    )
    account_map = repo.list_oauth_accounts_by_user_ids(session, [user.id for user in users])
    items = [
        SiteUserAdminRead(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            primary_auth_provider=user.primary_auth_provider,
            auth_mode="binding" if account_map.get(user.id) else "email",
            oauth_accounts=[
                SiteUserOAuthAccountAdminRead(
                    provider=account.provider,
                    provider_email=account.provider_email,
                    provider_display_name=account.provider_display_name,
                    created_at=account.created_at,
                )
                for account in account_map.get(user.id, [])
                if account.provider in ALLOWED_OAUTH_PROVIDERS
            ],
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
        )
        for user in users
    ]
    return items, total


def _enabled_oauth_providers(session: Session) -> list[str]:
    config = _get_site_auth_config_orm(session)
    visitor = _normalize_string_list(config.visitor_oauth_providers, ALLOWED_OAUTH_PROVIDERS)
    admin = [
        item
        for item in _normalize_string_list(config.admin_auth_methods, ALLOWED_ADMIN_AUTH_METHODS)
        if item in ALLOWED_OAUTH_PROVIDERS
    ]
    return _normalize_string_list([*visitor, *admin], ALLOWED_OAUTH_PROVIDERS)


def _email_login_enabled(session: Session) -> bool:
    config = _get_site_auth_config_orm(session)
    return bool(config.email_login_enabled or config.admin_email_enabled)


def _oauth_credentials(session: Session, provider: str) -> tuple[str, str]:
    settings = get_settings()
    config = _get_site_auth_config_orm(session)
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


def get_auth_state(session: Session, user: SiteUser | None) -> SiteAuthStateRead:
    return SiteAuthStateRead(
        authenticated=user is not None,
        user=_user_to_read(session, user) if user else None,
        email_login_enabled=_email_login_enabled(session),
        oauth_providers=_enabled_oauth_providers(session),
    )


def is_site_user_admin(session: Session, user: SiteUser) -> bool:
    return _resolve_admin_identity(session, user).is_admin


def get_admin_comment_identity(session: Session) -> tuple[str, str, str]:
    return (
        _resolve_admin_display_name(session),
        ADMIN_COMMENT_AVATAR_KEY,
        _resolve_admin_avatar_url(session),
    )


def create_site_session(session: Session, site_user_id: str, ttl_hours: int | None = None) -> str:
    settings = get_settings()
    ttl = ttl_hours or getattr(settings, "public_session_ttl_hours", SESSION_TTL_HOURS)
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(UTC) + timedelta(hours=ttl)
    repo.create_session(session, site_user_id=site_user_id, token=token, expires_at=expires_at)
    session.commit()
    return token


def validate_site_session_token(session: Session, token: str) -> SiteUser:
    site_session = repo.find_session_by_token(session, token)
    if site_session is None:
        raise AuthenticationFailed("Invalid or expired session token")
    now_utc = datetime.now(UTC)
    now = now_utc.replace(tzinfo=None) if site_session.expires_at.tzinfo is None else now_utc
    if site_session.expires_at < now:
        session.delete(site_session)
        session.commit()
        raise AuthenticationFailed("Session expired")
    user = repo.find_user_by_id(session, site_session.site_user_id)
    if user is None or not user.is_active:
        raise PermissionDenied("User not found or inactive")
    return user


def destroy_site_session(session: Session, token: str) -> None:
    existing = repo.find_session_by_token(session, token)
    if existing is None:
        return
    repo.delete_session(session, existing)
    session.commit()


def login_with_email(session: Session, payload: EmailLoginRequest) -> tuple[EmailLoginResponse, str | None]:
    if not _email_login_enabled(session):
        raise ValidationError("当前站点未启用邮箱登录。")

    normalized_email = _normalize_email(payload.email)
    if not normalized_email or "@" not in normalized_email:
        raise ValidationError("请输入有效邮箱。")

    existing = repo.find_user_by_email(session, normalized_email)
    if existing is not None:
        existing.last_login_at = datetime.now(UTC)
        session.commit()
        session.refresh(existing)
        token = create_site_session(session, existing.id)
        return (
            EmailLoginResponse(
                authenticated=True,
                requires_profile=False,
                user=_user_to_read(session, existing),
                suggested_display_name=None,
                avatar_candidates=[],
                avatar_batch=0,
                avatar_total_batches=1,
            ),
            token,
        )

    display_name = _normalize_display_name(payload.display_name)
    avatar_url = (payload.avatar_url or "").strip()
    if not display_name or not avatar_url:
        avatar_batch = build_avatar_candidate_batch(normalized_email)
        return (
            EmailLoginResponse(
                authenticated=False,
                requires_profile=True,
                user=None,
                suggested_display_name=suggest_display_name(normalized_email),
                avatar_candidates=avatar_batch.avatar_candidates,
                avatar_batch=avatar_batch.batch,
                avatar_total_batches=avatar_batch.total_batches,
            ),
            None,
        )

    user = repo.create_user(
        session,
        email=normalized_email,
        display_name=display_name,
        avatar_url=avatar_url,
        primary_auth_provider="email",
        last_login_at=datetime.now(UTC),
    )
    session.commit()
    session.refresh(user)
    token = create_site_session(session, user.id)
    return (
        EmailLoginResponse(
            authenticated=True,
            requires_profile=False,
            user=_user_to_read(session, user),
            suggested_display_name=None,
            avatar_candidates=[],
            avatar_batch=0,
            avatar_total_batches=1,
        ),
        token,
    )


def update_site_user_profile(
    session: Session,
    user: SiteUser,
    payload: SiteAuthProfileUpdateRequest,
) -> SiteAuthUserRead:
    display_name = _normalize_display_name(payload.display_name)
    avatar_url = (payload.avatar_url or "").strip()
    if not display_name:
        raise ValidationError("请输入显示昵称。")
    if not avatar_url:
        raise ValidationError("请选择头像。")

    user.display_name = display_name
    user.avatar_url = avatar_url
    session.commit()
    with suppress(Exception):
        sync_site_user_comment_profile(
            site_user_id=user.id,
            nick=user.display_name,
            avatar_url=user.avatar_url,
        )
    session.refresh(user)
    return _user_to_read(session, user)


def build_oauth_state_cookie(provider: str, state: str, return_to: str) -> str:
    payload = {"provider": provider, "state": state, "return_to": _normalize_return_to(return_to)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def parse_oauth_state_cookie(raw: str | None) -> OAuthStatePayload | None:
    if not raw:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
    except Exception:
        return None
    provider = str(payload.get("provider") or "").strip().lower()
    state = str(payload.get("state") or "").strip()
    return_to = _normalize_return_to(str(payload.get("return_to") or "/"))
    if provider not in {"google", "github"} or not state:
        return None
    return OAuthStatePayload(provider=provider, state=state, return_to=return_to)


def build_oauth_authorization_url(
    session: Session,
    provider: str,
    return_to: str,
    *,
    callback_url: str,
) -> tuple[str, str]:
    normalized = provider.strip().lower()
    state = secrets.token_urlsafe(24)

    if normalized not in _enabled_oauth_providers(session):
        raise ValidationError("当前站点未启用该登录方式。")

    if normalized == "github":
        client_id, _ = _oauth_credentials(session, "github")
        if not client_id:
            raise ValidationError("GitHub 登录尚未配置。")
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "scope": "read:user user:email",
                "state": state,
            }
        )
        auth_url = f"https://github.com/login/oauth/authorize?{params}"
        return auth_url, build_oauth_state_cookie("github", state, return_to)

    if normalized == "google":
        client_id, _ = _oauth_credentials(session, "google")
        if not client_id:
            raise ValidationError("Google 登录尚未配置。")
        params = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "online",
                "prompt": "select_account",
                "state": state,
            }
        )
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
        return auth_url, build_oauth_state_cookie("google", state, return_to)

    raise ValidationError("不支持的登录方式。")


def _exchange_github_code(session: Session, code: str, *, callback_url: str) -> OAuthProviderCallbackResult:
    client_id, client_secret = _oauth_credentials(session, "github")
    token_response = httpx.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": callback_url,
        },
        timeout=8.0,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("GitHub 登录失败。")

    user_response = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        timeout=8.0,
    )
    user_response.raise_for_status()
    user_payload = user_response.json()

    email_response = httpx.get(
        "https://api.github.com/user/emails",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        timeout=8.0,
    )
    email_response.raise_for_status()
    email_payload = email_response.json()
    primary_email = ""
    if isinstance(email_payload, list):
        primary = next((item for item in email_payload if item.get("primary")), None)
        if primary is None and email_payload:
            primary = email_payload[0]
        if primary:
            primary_email = str(primary.get("email") or "")

    return OAuthProviderCallbackResult(
        provider="github",
        email=_normalize_email(primary_email),
        display_name=_normalize_display_name(
            str(user_payload.get("name") or user_payload.get("login") or "GitHub User")
        ),
        avatar_url=str(user_payload.get("avatar_url") or ""),
        provider_subject=str(user_payload.get("id") or ""),
    )


def _exchange_google_code(session: Session, code: str, *, callback_url: str) -> OAuthProviderCallbackResult:
    client_id, client_secret = _oauth_credentials(session, "google")
    token_response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": callback_url,
        },
        timeout=8.0,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("Google 登录失败。")

    user_response = httpx.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=8.0,
    )
    user_response.raise_for_status()
    user_payload = user_response.json()

    return OAuthProviderCallbackResult(
        provider="google",
        email=_normalize_email(str(user_payload.get("email") or "")),
        display_name=_normalize_display_name(str(user_payload.get("name") or "Google User")),
        avatar_url=str(user_payload.get("picture") or ""),
        provider_subject=str(user_payload.get("sub") or ""),
    )


def complete_oauth_login(
    session: Session,
    provider: str,
    code: str,
    state: str,
    state_cookie: str | None,
    *,
    callback_url: str,
) -> tuple[str, str]:
    payload = parse_oauth_state_cookie(state_cookie)
    if payload is None or payload.provider != provider or payload.state != state:
        raise AuthenticationFailed("登录状态已失效，请重新开始。")

    if provider == "github":
        profile = _exchange_github_code(session, code, callback_url=callback_url)
    elif provider == "google":
        profile = _exchange_google_code(session, code, callback_url=callback_url)
    else:
        raise ValidationError("不支持的登录方式。")

    if not profile.email:
        raise ValidationError("当前登录方式没有返回可用邮箱，无法建立站点身份。")

    oauth_account = repo.find_oauth_account(session, provider=provider, provider_subject=profile.provider_subject)
    user = repo.find_user_by_email(session, profile.email)

    if oauth_account is not None:
        user = repo.find_user_by_id(session, oauth_account.site_user_id)

    if user is None:
        user = repo.create_user(
            session,
            email=profile.email,
            display_name=profile.display_name or suggest_display_name(profile.email),
            avatar_url=profile.avatar_url or build_avatar_candidates(profile.email, 1)[0].avatar_url,
            primary_auth_provider=provider,
            last_login_at=datetime.now(UTC),
        )
        session.flush()
    else:
        user.display_name = profile.display_name or user.display_name
        if profile.avatar_url:
            user.avatar_url = profile.avatar_url
        user.primary_auth_provider = provider
        user.last_login_at = datetime.now(UTC)

    if oauth_account is None:
        repo.create_oauth_account(
            session,
            site_user_id=user.id,
            provider=provider,
            provider_subject=profile.provider_subject,
            provider_email=profile.email,
            provider_display_name=profile.display_name,
            provider_avatar_url=profile.avatar_url,
        )
    else:
        oauth_account.provider_email = profile.email
        oauth_account.provider_display_name = profile.display_name
        oauth_account.provider_avatar_url = profile.avatar_url

    session.commit()
    session.refresh(user)
    token = create_site_session(session, user.id)
    return token, payload.return_to
