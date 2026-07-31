from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from aerisun.core.time import normalize_shanghai_datetime, shanghai_now
from aerisun.domain.content.models import PostEntry
from aerisun.domain.diary_access.service import (
    _mail_feedback_available,
    _oauth_providers_by_user_id,
    _remaining_seconds,
    get_site_owner_name,
)
from aerisun.domain.exceptions import AuthenticationFailed, PermissionDenied, ResourceNotFound, ValidationError
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.post_access.models import PostAccessRequest
from aerisun.domain.post_access.schemas import (
    PostAccessGrantedListRead,
    PostAccessGrantedRead,
    PostAccessRequestAdminList,
    PostAccessRequestAdminRead,
    PostAccessRequestAdminUpdate,
    PostAccessRequestCreate,
    PostAccessRequestRead,
    PostAccessStateRead,
)
from aerisun.domain.site_auth.models import SiteUser, SiteUserSession
from aerisun.domain.site_auth.service import is_site_user_admin
from aerisun.domain.site_config.models import SiteProfile

POST_ACCESS_APPROVAL_FEATURE_FLAG = "post_access_approval_enabled"
POST_ACCESS_STATUS_PENDING = "pending"
POST_ACCESS_STATUS_APPROVED = "approved"
POST_ACCESS_STATUS_REVOKED = "revoked"
DEFAULT_POST_ACCESS_DAYS = 7
logger = logging.getLogger("aerisun.post_access")


def _now() -> datetime:
    return shanghai_now()


def post_access_approval_enabled(session: Session) -> bool:
    flags = session.scalar(select(SiteProfile.feature_flags).limit(1))
    if not isinstance(flags, dict):
        return True
    return bool(flags.get(POST_ACCESS_APPROVAL_FEATURE_FLAG, True))


def _post_requires_approval(session: Session, post: PostEntry) -> bool:
    return post_access_approval_enabled(session) and post.visibility == "public" and bool(post.requires_approval)


def _public_post_by_slug(session: Session, slug: str) -> PostEntry:
    post = session.scalar(select(PostEntry).where(PostEntry.slug == slug).limit(1))
    if post is None or post.visibility != "public":
        raise ResourceNotFound(f"PostEntry with slug '{slug}' was not found")
    return post


def _request_has_active_access(item: PostAccessRequest, *, now: datetime | None = None) -> bool:
    if item.status != POST_ACCESS_STATUS_APPROVED or item.revoked_at is not None:
        return False
    expires_at = normalize_shanghai_datetime(item.expires_at) if item.expires_at is not None else None
    return expires_at is not None and expires_at > (now or _now())


def get_active_post_access_request(
    session: Session,
    *,
    post_id: str,
    site_user_id: str,
) -> PostAccessRequest | None:
    items = session.scalars(
        select(PostAccessRequest)
        .where(
            PostAccessRequest.post_id == post_id,
            PostAccessRequest.site_user_id == site_user_id,
            PostAccessRequest.status == POST_ACCESS_STATUS_APPROVED,
            PostAccessRequest.revoked_at.is_(None),
        )
        .order_by(PostAccessRequest.expires_at.desc(), PostAccessRequest.updated_at.desc())
    ).all()
    now = _now()
    return next((item for item in items if _request_has_active_access(item, now=now)), None)


def _latest_pending_request(session: Session, *, post_id: str, site_user_id: str) -> PostAccessRequest | None:
    return session.scalar(
        select(PostAccessRequest)
        .where(
            PostAccessRequest.post_id == post_id,
            PostAccessRequest.site_user_id == site_user_id,
            PostAccessRequest.status == POST_ACCESS_STATUS_PENDING,
        )
        .order_by(PostAccessRequest.updated_at.desc())
        .limit(1)
    )


def require_post_detail_access(
    session: Session,
    slug: str,
    current_user: SiteUser | None,
    current_site_session: SiteUserSession | None,
) -> bool:
    post = _public_post_by_slug(session, slug)
    if not _post_requires_approval(session, post):
        return False
    if current_user is None:
        raise AuthenticationFailed("请先登录。")
    if is_site_user_admin(session, current_user, current_site_session):
        return True
    if get_active_post_access_request(session, post_id=post.id, site_user_id=current_user.id) is not None:
        return True
    raise PermissionDenied(f"您没有权限查看《{post.title}》")


def get_post_access_state(
    session: Session,
    slug: str,
    current_user: SiteUser | None,
    current_site_session: SiteUserSession | None,
) -> PostAccessStateRead:
    post = _public_post_by_slug(session, slug)
    enabled = post_access_approval_enabled(session)
    requires_approval = enabled and bool(post.requires_approval)
    owner_name = get_site_owner_name(session)
    mail_feedback_available = _mail_feedback_available(session)
    if current_user is None:
        return PostAccessStateRead(
            authenticated=False,
            approval_enabled=enabled,
            requires_approval=requires_approval,
            has_access=not requires_approval,
            owner_name=owner_name,
            post_title=post.title,
            mail_feedback_available=mail_feedback_available,
        )

    active_request = get_active_post_access_request(
        session,
        post_id=post.id,
        site_user_id=current_user.id,
    )
    is_admin = is_site_user_admin(session, current_user, current_site_session)
    has_access = not requires_approval or is_admin or active_request is not None
    expires_at = None if is_admin and active_request is None else active_request.expires_at if active_request else None
    pending = _latest_pending_request(session, post_id=post.id, site_user_id=current_user.id)
    return PostAccessStateRead(
        authenticated=True,
        approval_enabled=enabled,
        requires_approval=requires_approval,
        has_access=has_access,
        owner_name=owner_name,
        post_title=post.title,
        mail_feedback_available=mail_feedback_available,
        access_expires_at=expires_at,
        remaining_seconds=_remaining_seconds(expires_at),
        pending_request_id=pending.id if pending is not None else None,
    )


def list_current_user_post_access(
    session: Session,
    current_user: SiteUser,
) -> PostAccessGrantedListRead:
    if not post_access_approval_enabled(session):
        return PostAccessGrantedListRead(items=[])

    now = _now()
    rows = session.execute(
        select(PostAccessRequest, PostEntry)
        .join(PostEntry, PostEntry.id == PostAccessRequest.post_id)
        .where(
            PostAccessRequest.site_user_id == current_user.id,
            PostAccessRequest.status == POST_ACCESS_STATUS_APPROVED,
            PostAccessRequest.revoked_at.is_(None),
            PostAccessRequest.expires_at.is_not(None),
            PostAccessRequest.expires_at > now,
            PostEntry.visibility == "public",
            PostEntry.requires_approval.is_(True),
        )
        .order_by(PostEntry.title.asc(), PostAccessRequest.expires_at.desc())
    ).all()
    items_by_post_id: dict[str, PostAccessGrantedRead] = {}
    for request, post in rows:
        expires_at = request.expires_at
        remaining_seconds = _remaining_seconds(expires_at)
        if expires_at is None or remaining_seconds is None or remaining_seconds <= 0:
            continue
        items_by_post_id.setdefault(
            post.id,
            PostAccessGrantedRead(
                slug=post.slug,
                title=post.title,
                access_expires_at=expires_at,
                remaining_seconds=remaining_seconds,
            ),
        )
    return PostAccessGrantedListRead(items=list(items_by_post_id.values()))


def submit_post_access_request(
    session: Session,
    slug: str,
    current_user: SiteUser,
    payload: PostAccessRequestCreate,
) -> PostAccessRequestRead:
    post = _public_post_by_slug(session, slug)
    if not _post_requires_approval(session, post):
        raise ValidationError("该文章当前不需要申请查看。")
    reason = " ".join(payload.reason.split()).strip()
    if not reason:
        raise ValidationError("请填写申请理由。")
    if len(reason) > 1000:
        raise ValidationError("申请理由不能超过 1000 个字符。")

    item = _latest_pending_request(session, post_id=post.id, site_user_id=current_user.id)
    if item is None:
        item = PostAccessRequest(
            post_id=post.id,
            site_user_id=current_user.id,
            reason=reason,
            status=POST_ACCESS_STATUS_PENDING,
        )
        session.add(item)
    else:
        item.reason = reason
    session.commit()
    session.refresh(item)
    return _to_request_read(item)


def list_post_access_requests_admin(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    latest_requests = select(
        PostAccessRequest.id.label("request_id"),
        func.row_number()
        .over(
            partition_by=(PostAccessRequest.post_id, PostAccessRequest.site_user_id),
            order_by=(PostAccessRequest.created_at.desc(), PostAccessRequest.id.desc()),
        )
        .label("row_number"),
    ).subquery()
    latest_only = latest_requests.c.row_number == 1
    now = _now()
    active_access = and_(
        PostAccessRequest.status == POST_ACCESS_STATUS_APPROVED,
        PostAccessRequest.revoked_at.is_(None),
        PostAccessRequest.expires_at.is_not(None),
        PostAccessRequest.expires_at > now,
    )
    people_total, pending_total, authorized_total = session.execute(
        select(
            func.count(PostAccessRequest.id),
            func.coalesce(
                func.sum(case((PostAccessRequest.status == POST_ACCESS_STATUS_PENDING, 1), else_=0)),
                0,
            ),
            func.coalesce(func.sum(case((active_access, 1), else_=0)), 0),
        )
        .join(latest_requests, latest_requests.c.request_id == PostAccessRequest.id)
        .where(latest_only)
    ).one()
    rows = session.execute(
        select(PostAccessRequest, SiteUser, PostEntry)
        .join(SiteUser, SiteUser.id == PostAccessRequest.site_user_id)
        .join(PostEntry, PostEntry.id == PostAccessRequest.post_id)
        .join(latest_requests, latest_requests.c.request_id == PostAccessRequest.id)
        .where(latest_only)
        .order_by(PostAccessRequest.created_at.desc(), PostAccessRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    users = [user for _item, user, _post in rows]
    providers_by_user = _oauth_providers_by_user_id(session, [user.id for user in users])
    return PostAccessRequestAdminList(
        items=[
            _to_admin_read(
                item,
                post,
                user,
                providers_by_user.get(user.id, []),
                item if _request_has_active_access(item, now=now) else None,
            )
            for item, user, post in rows
        ],
        total=int(people_total),
        page=page,
        page_size=page_size,
        people_total=int(people_total),
        pending_total=int(pending_total),
        authorized_total=int(authorized_total),
    ).model_dump()


def update_post_access_request_admin(
    session: Session,
    request_id: str,
    payload: PostAccessRequestAdminUpdate,
    admin: AdminUser,
) -> PostAccessRequestAdminRead:
    item = session.get(PostAccessRequest, request_id)
    if item is None:
        raise ResourceNotFound("Post access request not found")
    now = _now()
    should_send_feedback = False
    if payload.revoke_access or payload.grant_access is False:
        item.status = POST_ACCESS_STATUS_REVOKED
        item.revoked_at = now
        item.reviewed_at = now
        item.reviewed_by_admin_id = admin.id
        should_send_feedback = True
    elif payload.grant_access is True:
        expires_at = normalize_shanghai_datetime(payload.expires_at or (now + timedelta(days=DEFAULT_POST_ACCESS_DAYS)))
        if expires_at <= now:
            raise ValidationError("授权到期时间必须晚于当前时间。")
        item.status = POST_ACCESS_STATUS_APPROVED
        item.granted_at = item.granted_at or now
        item.expires_at = expires_at
        item.revoked_at = None
        item.reviewed_at = now
        item.reviewed_by_admin_id = admin.id
        should_send_feedback = True
    elif payload.expires_at is not None:
        if item.status != POST_ACCESS_STATUS_APPROVED or item.revoked_at is not None:
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
    post = session.get(PostEntry, item.post_id)
    if user is None or post is None:
        raise ResourceNotFound("Post access request target not found")
    if should_send_feedback:
        try:
            from aerisun.domain.subscription.service import send_post_access_feedback_notification

            send_post_access_feedback_notification(session, request=item, user=user, post=post)
        except Exception:
            logger.warning("Failed to send post access feedback notification", exc_info=True)
    providers = _oauth_providers_by_user_id(session, [user.id]).get(user.id, [])
    active = get_active_post_access_request(session, post_id=post.id, site_user_id=user.id)
    return _to_admin_read(item, post, user, providers, active)


def _to_request_read(item: PostAccessRequest) -> PostAccessRequestRead:
    active = _request_has_active_access(item)
    expires_at = item.expires_at if active else None
    return PostAccessRequestRead(
        id=item.id,
        post_id=item.post_id,
        reason=item.reason,
        status=item.status,
        has_access=active,
        access_expires_at=expires_at,
        remaining_seconds=_remaining_seconds(expires_at),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_admin_read(
    item: PostAccessRequest,
    post: PostEntry,
    user: SiteUser,
    oauth_providers: list[str],
    active_request: PostAccessRequest | None,
) -> PostAccessRequestAdminRead:
    expires_at = active_request.expires_at if active_request is not None else None
    return PostAccessRequestAdminRead(
        id=item.id,
        post_id=post.id,
        post_slug=post.slug,
        post_title=post.title,
        site_user_id=user.id,
        visitor_email=user.email,
        visitor_display_name=user.display_name,
        visitor_avatar_url=user.avatar_url,
        visitor_auth_provider=user.primary_auth_provider,
        visitor_oauth_providers=oauth_providers,
        reason=item.reason,
        status=item.status,
        has_access=active_request is not None,
        access_granted_at=item.granted_at,
        access_expires_at=expires_at,
        access_revoked_at=item.revoked_at,
        remaining_seconds=_remaining_seconds(expires_at),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
