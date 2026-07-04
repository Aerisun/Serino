from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.core.time import normalize_shanghai_datetime, shanghai_now
from aerisun.domain.diary_access.models import DiaryAccessRequest
from aerisun.domain.diary_access.schemas import (
    DiaryAccessRequestAdminRead,
    DiaryAccessRequestAdminUpdate,
    DiaryAccessRequestCreate,
    DiaryAccessRequestRead,
    DiaryAccessStateRead,
)
from aerisun.domain.exceptions import AuthenticationFailed, PermissionDenied, ResourceNotFound, ValidationError
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.site_auth.models import SiteUser, SiteUserOAuthAccount, SiteUserSession
from aerisun.domain.site_auth.service import is_site_user_admin
from aerisun.domain.site_config.models import SiteProfile

DIARY_PRIVATE_FEATURE_FLAG = "diary_private_enabled"
DIARY_ACCESS_STATUS_PENDING = "pending"
DIARY_ACCESS_STATUS_APPROVED = "approved"
DIARY_ACCESS_STATUS_REVOKED = "revoked"
DEFAULT_DIARY_ACCESS_DAYS = 7
logger = logging.getLogger("aerisun.diary_access")


def _now() -> datetime:
    return shanghai_now()


def _normalize(value: datetime | None) -> datetime | None:
    return normalize_shanghai_datetime(value) if value is not None else None


def _remaining_seconds(expires_at: datetime | None, *, now: datetime | None = None) -> int | None:
    normalized_expires_at = _normalize(expires_at)
    if normalized_expires_at is None:
        return None
    current = now or _now()
    return max(0, int((normalized_expires_at - current).total_seconds()))


def _request_has_active_access(item: DiaryAccessRequest, *, now: datetime | None = None) -> bool:
    if item.status != DIARY_ACCESS_STATUS_APPROVED:
        return False
    if item.revoked_at is not None:
        return False
    expires_at = _normalize(item.expires_at)
    return expires_at is not None and expires_at > (now or _now())


def get_site_owner_name(session: Session) -> str:
    profile = session.scalar(select(SiteProfile).limit(1))
    if profile is None:
        return "站长"
    return (profile.title or profile.name or "").strip() or "站长"


def diary_private_enabled(session: Session) -> bool:
    flags = session.scalar(select(SiteProfile.feature_flags).limit(1))
    if not isinstance(flags, dict):
        return True
    return bool(flags.get(DIARY_PRIVATE_FEATURE_FLAG, True))


def _mail_feedback_available(session: Session) -> bool:
    try:
        from aerisun.domain.subscription.service import diary_access_mail_feedback_available

        return diary_access_mail_feedback_available(session)
    except Exception:
        logger.warning("Failed to resolve diary access mail feedback availability", exc_info=True)
        return False


def get_active_diary_access_request(session: Session, site_user_id: str) -> DiaryAccessRequest | None:
    items = session.scalars(
        select(DiaryAccessRequest)
        .where(
            DiaryAccessRequest.site_user_id == site_user_id,
            DiaryAccessRequest.status == DIARY_ACCESS_STATUS_APPROVED,
            DiaryAccessRequest.revoked_at.is_(None),
        )
        .order_by(DiaryAccessRequest.expires_at.desc(), DiaryAccessRequest.updated_at.desc())
    ).all()
    now = _now()
    for item in items:
        if _request_has_active_access(item, now=now):
            return item
    return None


def site_user_has_active_diary_access(session: Session, user: SiteUser | None) -> bool:
    return user is not None and get_active_diary_access_request(session, user.id) is not None


def current_site_user_can_view_diary(
    session: Session,
    current_user: SiteUser | None,
    current_site_session: SiteUserSession | None,
) -> bool:
    if not diary_private_enabled(session):
        return True
    if current_user is None:
        return False
    if is_site_user_admin(session, current_user, current_site_session):
        return True
    return site_user_has_active_diary_access(session, current_user)


def _remove_diary_subscription_after_access_loss(session: Session, site_user_id: str) -> int:
    try:
        from aerisun.domain.subscription.service import remove_diary_subscription_for_site_user

        return remove_diary_subscription_for_site_user(session, site_user_id)
    except Exception:
        logger.warning("Failed to remove diary subscription after access loss", exc_info=True)
        return 0


def require_diary_detail_access(
    session: Session,
    current_user: SiteUser | None,
    current_site_session: SiteUserSession | None,
) -> None:
    if not diary_private_enabled(session):
        return
    if current_user is None:
        raise AuthenticationFailed("请先登录。")
    if current_site_user_can_view_diary(session, current_user, current_site_session):
        return
    if _remove_diary_subscription_after_access_loss(session, current_user.id):
        session.commit()
    raise PermissionDenied(f"您没有权限查看 {get_site_owner_name(session)} 的日记")


def _latest_pending_request(session: Session, site_user_id: str) -> DiaryAccessRequest | None:
    return session.scalar(
        select(DiaryAccessRequest)
        .where(
            DiaryAccessRequest.site_user_id == site_user_id,
            DiaryAccessRequest.status == DIARY_ACCESS_STATUS_PENDING,
        )
        .order_by(DiaryAccessRequest.updated_at.desc())
        .limit(1)
    )


def _pending_request_id(session: Session, site_user_id: str) -> str | None:
    item = _latest_pending_request(session, site_user_id)
    return item.id if item is not None else None


def get_diary_access_state(
    session: Session,
    current_user: SiteUser | None,
    current_site_session: SiteUserSession | None,
) -> DiaryAccessStateRead:
    private_enabled = diary_private_enabled(session)
    owner_name = get_site_owner_name(session)
    mail_feedback_available = _mail_feedback_available(session)
    if current_user is None:
        return DiaryAccessStateRead(
            authenticated=False,
            diary_private_enabled=private_enabled,
            has_access=not private_enabled,
            owner_name=owner_name,
            mail_feedback_available=mail_feedback_available,
        )

    active_request = get_active_diary_access_request(session, current_user.id)
    is_admin = is_site_user_admin(session, current_user, current_site_session)
    has_access = not private_enabled or is_admin or active_request is not None
    if private_enabled and not has_access and _remove_diary_subscription_after_access_loss(session, current_user.id):
        session.commit()
    expires_at = None if is_admin and active_request is None else active_request.expires_at if active_request else None
    return DiaryAccessStateRead(
        authenticated=True,
        diary_private_enabled=private_enabled,
        has_access=has_access,
        owner_name=owner_name,
        mail_feedback_available=mail_feedback_available,
        access_expires_at=expires_at,
        remaining_seconds=_remaining_seconds(expires_at),
        pending_request_id=_pending_request_id(session, current_user.id),
    )


def submit_diary_access_request(
    session: Session,
    current_user: SiteUser,
    payload: DiaryAccessRequestCreate,
) -> DiaryAccessRequestRead:
    reason = " ".join(payload.reason.split()).strip()
    if not reason:
        raise ValidationError("请填写申请理由。")
    if len(reason) > 1000:
        raise ValidationError("申请理由不能超过 1000 个字符。")

    item = _latest_pending_request(session, current_user.id)
    if item is None:
        item = DiaryAccessRequest(
            site_user_id=current_user.id,
            reason=reason,
            status=DIARY_ACCESS_STATUS_PENDING,
        )
        session.add(item)
    else:
        item.reason = reason

    session.commit()
    session.refresh(item)
    return _to_request_read(item)


def _oauth_providers_by_user_id(session: Session, user_ids: Iterable[str]) -> dict[str, list[str]]:
    ids = list(user_ids)
    if not ids:
        return {}
    rows = session.execute(
        select(SiteUserOAuthAccount.site_user_id, SiteUserOAuthAccount.provider)
        .where(SiteUserOAuthAccount.site_user_id.in_(ids))
        .order_by(SiteUserOAuthAccount.provider.asc())
    ).all()
    result: dict[str, list[str]] = {}
    for user_id, provider in rows:
        result.setdefault(user_id, [])
        if provider not in result[user_id]:
            result[user_id].append(provider)
    return result


def _active_access_by_user_id(
    session: Session,
    user_ids: Iterable[str],
) -> dict[str, DiaryAccessRequest]:
    result: dict[str, DiaryAccessRequest] = {}
    for user_id in user_ids:
        active = get_active_diary_access_request(session, user_id)
        if active is not None:
            result[user_id] = active
    return result


def list_diary_access_requests_admin(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total = session.scalar(select(func.count()).select_from(DiaryAccessRequest)) or 0
    rows = session.execute(
        select(DiaryAccessRequest, SiteUser)
        .join(SiteUser, SiteUser.id == DiaryAccessRequest.site_user_id)
        .order_by(DiaryAccessRequest.updated_at.desc(), DiaryAccessRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    users = [user for _item, user in rows]
    provider_map = _oauth_providers_by_user_id(session, [user.id for user in users])
    active_map = _active_access_by_user_id(session, [user.id for user in users])
    return {
        "items": [
            _to_admin_read(item, user, provider_map.get(user.id, []), active_map.get(user.id)) for item, user in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def update_diary_access_request_admin(
    session: Session,
    request_id: str,
    payload: DiaryAccessRequestAdminUpdate,
    admin: AdminUser,
) -> DiaryAccessRequestAdminRead:
    item = session.get(DiaryAccessRequest, request_id)
    if item is None:
        raise ResourceNotFound("Diary access request not found")

    now = _now()
    should_send_feedback = False
    if payload.revoke_access or payload.grant_access is False:
        item.status = DIARY_ACCESS_STATUS_REVOKED
        item.revoked_at = now
        item.reviewed_at = now
        item.reviewed_by_admin_id = admin.id
        _remove_diary_subscription_after_access_loss(session, item.site_user_id)
        should_send_feedback = True
    elif payload.grant_access is True:
        expires_at = payload.expires_at or (now + timedelta(days=DEFAULT_DIARY_ACCESS_DAYS))
        expires_at = normalize_shanghai_datetime(expires_at)
        if expires_at <= now:
            raise ValidationError("授权到期时间必须晚于当前时间。")
        item.status = DIARY_ACCESS_STATUS_APPROVED
        item.granted_at = item.granted_at or now
        item.expires_at = expires_at
        item.revoked_at = None
        item.reviewed_at = now
        item.reviewed_by_admin_id = admin.id
        should_send_feedback = True
    elif payload.expires_at is not None:
        if item.status != DIARY_ACCESS_STATUS_APPROVED or item.revoked_at is not None:
            raise ValidationError("只能延长已有权限。")
        expires_at = normalize_shanghai_datetime(payload.expires_at)
        if expires_at <= now:
            raise ValidationError("授权到期时间必须晚于当前时间。")
        item.expires_at = expires_at
        item.reviewed_at = now
        item.reviewed_by_admin_id = admin.id
        should_send_feedback = True

    session.commit()
    session.refresh(item)
    user = session.get(SiteUser, item.site_user_id)
    if user is None:
        raise ResourceNotFound("Site user not found")
    if should_send_feedback:
        try:
            from aerisun.domain.subscription.service import send_diary_access_feedback_notification

            send_diary_access_feedback_notification(session, request=item, user=user)
        except Exception:
            logger.warning("Failed to send diary access feedback notification", exc_info=True)
    providers = _oauth_providers_by_user_id(session, [user.id]).get(user.id, [])
    active = get_active_diary_access_request(session, user.id)
    return _to_admin_read(item, user, providers, active)


def _to_request_read(item: DiaryAccessRequest) -> DiaryAccessRequestRead:
    active = _request_has_active_access(item)
    expires_at = item.expires_at if active else None
    return DiaryAccessRequestRead(
        id=item.id,
        reason=item.reason,
        status=item.status,
        has_access=active,
        access_expires_at=expires_at,
        remaining_seconds=_remaining_seconds(expires_at),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_admin_read(
    item: DiaryAccessRequest,
    user: SiteUser,
    oauth_providers: list[str],
    active_request: DiaryAccessRequest | None,
) -> DiaryAccessRequestAdminRead:
    active = active_request is not None
    expires_at = active_request.expires_at if active_request is not None else None
    return DiaryAccessRequestAdminRead(
        id=item.id,
        site_user_id=user.id,
        visitor_email=user.email,
        visitor_display_name=user.display_name,
        visitor_avatar_url=user.avatar_url,
        visitor_auth_provider=user.primary_auth_provider,
        visitor_oauth_providers=oauth_providers,
        reason=item.reason,
        status=item.status,
        has_access=active,
        access_granted_at=item.granted_at,
        access_expires_at=expires_at,
        access_revoked_at=item.revoked_at,
        remaining_seconds=_remaining_seconds(expires_at),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
