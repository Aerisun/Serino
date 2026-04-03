from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ValidationError
from aerisun.domain.media.models import Asset
from aerisun.domain.site_auth import repository as repo
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.schemas import (
    EmailLoginRequest,
    EmailLoginResponse,
    SiteAuthAvatarCandidate,
    SiteAuthAvatarCandidateBatchRead,
    SiteAuthProfileUpdateRequest,
    SiteAuthStateRead,
    SiteAuthUserRead,
)
from aerisun.domain.site_config import repository as site_config_repo
from aerisun.domain.waline.service import sync_site_user_comment_profile

from .config_service import (
    admin_console_auth_method_enabled,
    email_login_enabled,
    enabled_visitor_oauth_providers,
    validate_admin_email_password,
)
from .sessions import create_site_session
from .shared import normalize_display_name, normalize_email

AVATAR_PICKER_COUNT = 12
AVATAR_POOL_SIZE = 1000
DICEBEAR_NOTIONISTS_BASE_URL = "https://api.dicebear.com/9.x/notionists/svg"
ADMIN_COMMENT_AVATAR_KEY = "site-admin"


@dataclass(slots=True)
class ResolvedAdminIdentity:
    is_admin: bool
    effective_display_name: str
    effective_avatar_url: str


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
    normalized_identity = normalize_email(identity) or "visitor"
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


def avatar_seed(identity: str, index: int) -> str:
    return f"{_avatar_hash(f'{identity}:{index}'):08x}"


def avatar_url_for_seed(seed: str) -> str:
    return f"{DICEBEAR_NOTIONISTS_BASE_URL}?seed={seed}"


def build_avatar_candidates(
    identity: str,
    count: int = AVATAR_PICKER_COUNT,
    batch: int = 0,
) -> list[SiteAuthAvatarCandidate]:
    normalized_identity = normalize_email(identity) or "visitor"
    candidates: list[SiteAuthAvatarCandidate] = []
    indexes, _, _ = _resolve_avatar_batch(normalized_identity, batch, count)
    for pool_index in indexes:
        seed = avatar_seed(normalized_identity, pool_index)
        candidates.append(
            SiteAuthAvatarCandidate(
                key=seed,
                label=f"Notionists {pool_index:03d}",
                avatar_url=avatar_url_for_seed(seed),
            )
        )
    return candidates


def build_avatar_candidate_batch(
    identity: str,
    *,
    batch: int = 0,
    count: int = AVATAR_PICKER_COUNT,
) -> SiteAuthAvatarCandidateBatchRead:
    normalized_identity = normalize_email(identity)
    if not normalized_identity or "@" not in normalized_identity:
        raise ValidationError("请输入有效邮箱。")

    indexes, normalized_batch, total_batches = _resolve_avatar_batch(normalized_identity, batch, count)
    candidates: list[SiteAuthAvatarCandidate] = []
    for pool_index in indexes:
        seed = avatar_seed(normalized_identity, pool_index)
        candidates.append(
            SiteAuthAvatarCandidate(
                key=seed,
                label=f"Notionists {pool_index:03d}",
                avatar_url=avatar_url_for_seed(seed),
            )
        )

    return SiteAuthAvatarCandidateBatchRead(
        batch=normalized_batch,
        total_batches=total_batches,
        avatar_candidates=candidates,
    )


def suggest_display_name(email: str) -> str:
    local_part = normalize_email(email).split("@", 1)[0]
    base = local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return normalize_display_name(base.title() or "Visitor") or "Visitor"


def resolve_admin_display_name(session: Session) -> str:
    site = site_config_repo.find_site_profile(session)
    for candidate in (
        site.name if site else "",
        site.title if site else "",
    ):
        resolved = normalize_display_name(candidate)
        if resolved:
            return resolved
    return "管理员"


def resolve_admin_avatar_url(session: Session) -> str:
    site = site_config_repo.find_site_profile(session)
    for candidate in (
        site.hero_image_url if site else "",
        site.hero_poster_url if site else "",
    ):
        resolved = str(candidate or "").strip()
        if resolved:
            return resolved

    asset = session.query(Asset).filter(Asset.category == "hero-image").order_by(Asset.created_at.asc()).first()
    if asset is not None:
        resource_key = str(asset.resource_key or "").strip()
        if resource_key:
            return f"/media/{resource_key}"
    seed = avatar_seed(resolve_admin_display_name(session).lower(), 0)
    return avatar_url_for_seed(seed)


def resolve_admin_identity(
    session: Session,
    user: SiteUser,
    site_session: SiteUserSession | None = None,
    admin_verified_provider: str | None = None,
) -> ResolvedAdminIdentity:
    verified_provider = (
        (site_session.admin_verified_provider or "").strip().lower()
        if site_session
        else (admin_verified_provider or "").strip().lower()
    )
    if not verified_provider:
        return ResolvedAdminIdentity(
            is_admin=False,
            effective_display_name=user.display_name,
            effective_avatar_url=user.avatar_url,
        )
    identity = repo.find_admin_identity_for_user_provider(
        session,
        site_user_id=user.id,
        provider=verified_provider,
    )
    if identity is None or not identity.admin_user_id:
        return ResolvedAdminIdentity(
            is_admin=False,
            effective_display_name=user.display_name,
            effective_avatar_url=user.avatar_url,
        )
    return ResolvedAdminIdentity(
        is_admin=True,
        effective_display_name=resolve_admin_display_name(session),
        effective_avatar_url=resolve_admin_avatar_url(session),
    )


def user_to_read(
    session: Session,
    user: SiteUser,
    site_session: SiteUserSession | None = None,
    admin_verified_provider: str | None = None,
) -> SiteAuthUserRead:
    verified_provider = (
        (site_session.admin_verified_provider or "").strip().lower()
        if site_session
        else (admin_verified_provider or "").strip().lower()
    )
    admin_identity = resolve_admin_identity(
        session,
        user,
        site_session,
        admin_verified_provider=admin_verified_provider,
    )
    return SiteAuthUserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        effective_display_name=admin_identity.effective_display_name,
        effective_avatar_url=admin_identity.effective_avatar_url,
        primary_auth_provider=user.primary_auth_provider,
        is_admin=admin_identity.is_admin,
        can_access_admin_console=bool(
            admin_identity.is_admin and admin_console_auth_method_enabled(session, verified_provider)
        ),
        last_login_at=user.last_login_at,
    )


def get_auth_state(
    session: Session,
    user: SiteUser | None,
    site_session: SiteUserSession | None = None,
) -> SiteAuthStateRead:
    return SiteAuthStateRead(
        authenticated=user is not None,
        user=user_to_read(session, user, site_session) if user else None,
        email_login_enabled=email_login_enabled(session),
        oauth_providers=enabled_visitor_oauth_providers(session),
    )


def is_site_user_admin(
    session: Session,
    user: SiteUser,
    site_session: SiteUserSession | None = None,
) -> bool:
    return resolve_admin_identity(session, user, site_session).is_admin


def get_admin_comment_identity(session: Session) -> tuple[str, str, str]:
    return (
        resolve_admin_display_name(session),
        ADMIN_COMMENT_AVATAR_KEY,
        resolve_admin_avatar_url(session),
    )


def login_with_email(session: Session, payload: EmailLoginRequest) -> tuple[EmailLoginResponse, str | None]:
    if not email_login_enabled(session):
        raise ValidationError("当前站点未启用邮箱登录。")

    normalized_email = normalize_email(payload.email)
    if not normalized_email or "@" not in normalized_email:
        raise ValidationError("请输入有效邮箱。")

    admin_identity = repo.find_admin_email_identity(session, email=normalized_email)
    admin_verified_provider = None
    if admin_identity is not None and admin_identity.admin_user_id:
        provided_password = (payload.admin_password or "").strip()
        if not provided_password:
            return (
                EmailLoginResponse(
                    authenticated=False,
                    requires_profile=False,
                    requires_admin_password=True,
                    user=None,
                    suggested_display_name=None,
                    avatar_candidates=[],
                    avatar_batch=0,
                    avatar_total_batches=1,
                ),
                None,
            )
        validate_admin_email_password(session, provided_password)
        admin_verified_provider = "email"

    existing = repo.find_user_by_email(session, normalized_email)
    if existing is not None:
        from datetime import UTC, datetime

        existing.last_login_at = datetime.now(UTC)
        session.commit()
        session.refresh(existing)
        token = create_site_session(
            session,
            existing.id,
            admin_verified_provider=admin_verified_provider,
        )
        return (
            EmailLoginResponse(
                authenticated=True,
                requires_profile=False,
                requires_admin_password=False,
                user=user_to_read(
                    session,
                    existing,
                    admin_verified_provider=admin_verified_provider,
                ),
                suggested_display_name=None,
                avatar_candidates=[],
                avatar_batch=0,
                avatar_total_batches=1,
            ),
            token,
        )

    display_name = normalize_display_name(payload.display_name)
    avatar_url = (payload.avatar_url or "").strip()
    if not display_name or not avatar_url:
        avatar_batch = build_avatar_candidate_batch(normalized_email)
        return (
            EmailLoginResponse(
                authenticated=False,
                requires_profile=True,
                requires_admin_password=False,
                user=None,
                suggested_display_name=suggest_display_name(normalized_email),
                avatar_candidates=avatar_batch.avatar_candidates,
                avatar_batch=avatar_batch.batch,
                avatar_total_batches=avatar_batch.total_batches,
            ),
            None,
        )

    from datetime import UTC, datetime

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
    token = create_site_session(
        session,
        user.id,
        admin_verified_provider=admin_verified_provider,
    )
    return (
        EmailLoginResponse(
            authenticated=True,
            requires_profile=False,
            requires_admin_password=False,
            user=user_to_read(
                session,
                user,
                admin_verified_provider=admin_verified_provider,
            ),
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
    site_session: SiteUserSession | None = None,
) -> SiteAuthUserRead:
    from aerisun.domain.automation.events import emit_site_user_profile_updated

    display_name = normalize_display_name(payload.display_name)
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
    emit_site_user_profile_updated(
        session,
        site_user_id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )
    return user_to_read(session, user, site_session)
