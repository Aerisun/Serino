from __future__ import annotations

import base64
import logging
import smtplib
from datetime import datetime
from string import Formatter
from email.message import EmailMessage
from uuid import uuid4

import httpx
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from aerisun.core.base import utcnow
from aerisun.core.db import get_session_factory
from aerisun.core.settings import Settings, get_settings
from aerisun.domain.content.feed_service import get_feed_definition, list_feed_definitions
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.site_config import repository as site_config_repo
from aerisun.domain.site_auth.models import SiteUser, SiteUserOAuthAccount

from .models import (
    ContentNotification,
    ContentNotificationDelivery,
    ContentSubscriber,
    ContentSubscriptionConfig,
)
from .schemas import (
    ContentNotificationDeliveryAdminRead,
    ContentSubscriberAdminRead,
    ContentSubscriptionConfigAdminRead,
    ContentSubscriptionConfigAdminUpdate,
    ContentSubscriptionPublicCreate,
    ContentSubscriptionPublicRead,
    ContentSubscriptionPublicStatusRead,
    ContentSubscriptionPublicUnsubscribeResult,
    ContentSubscriptionTestResult,
)

logger = logging.getLogger("aerisun.subscription")
SUBSCRIPTION_TEST_RECIPIENT = "do-not-reply@course.pku.edu.cn"
SMTP_AUTH_MODE_PASSWORD = "password"
SMTP_AUTH_MODE_MICROSOFT_OAUTH2 = "microsoft_oauth2"
MICROSOFT_SMTP_SCOPE = "offline_access https://outlook.office.com/SMTP.Send"
CONTENT_TYPE_LABELS = {
    "posts": "文章",
    "diary": "日记",
    "thoughts": "想法",
    "excerpts": "摘录",
}

DEFAULT_SUBJECT_TEMPLATE = "[{site_name}] {content_title}"
DEFAULT_BODY_TEMPLATE = (
    "{site_name} 有新的{content_type_label}内容发布。\n\n"
    "{content_title}\n"
    "{content_summary}\n\n"
    "阅读链接：{content_url}\n"
    "RSS：{feed_url}"
)

TEMPLATE_ALLOWED_KEYS = {
    "site_name",
    "content_type",
    "content_type_label",
    "content_title",
    "content_summary",
    "content_url",
    "feed_url",
}

DEFAULT_ALLOWED_CONTENT_TYPES = ["posts", "diary", "thoughts", "excerpts"]

CONTENT_MODELS: dict[str, type] = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}

SMTP_SETTING_KEYS = {
    "smtp_auth_mode",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_password",
    "smtp_oauth_tenant",
    "smtp_oauth_client_id",
    "smtp_oauth_client_secret",
    "smtp_oauth_refresh_token",
    "smtp_from_email",
    "smtp_from_name",
    "smtp_reply_to",
    "smtp_use_tls",
    "smtp_use_ssl",
}


def _allowed_smtp_auth_modes() -> set[str]:
    return {SMTP_AUTH_MODE_PASSWORD, SMTP_AUTH_MODE_MICROSOFT_OAUTH2}


def _normalize_smtp_auth_mode(value: str | None) -> str:
    normalized = (value or SMTP_AUTH_MODE_PASSWORD).strip().lower()
    if normalized not in _allowed_smtp_auth_modes():
        raise ValidationError("不支持的 SMTP 认证方式")
    return normalized


def _allowed_content_types() -> list[str]:
    return [definition.key for definition in list_feed_definitions()]


def _normalize_content_types(values: list[str]) -> list[str]:
    allowed = set(_allowed_content_types())
    normalized = sorted({str(value).strip() for value in values if str(value).strip()})
    invalid = [value for value in normalized if value not in allowed]
    if invalid:
        raise ValidationError(f"Unsupported subscription content types: {', '.join(invalid)}")
    if not normalized:
        raise ValidationError("请至少选择一种订阅内容")
    return normalized


def _normalize_allowed_content_types(values: list[str]) -> list[str]:
    normalized = _normalize_content_types(values)
    if not normalized:
        raise ValidationError("请至少开放一种订阅内容")
    return normalized


def _config_allowed_content_types(config: ContentSubscriptionConfig) -> list[str]:
    configured = list(config.allowed_content_types or [])
    if not configured:
        return list(DEFAULT_ALLOWED_CONTENT_TYPES)
    return _normalize_allowed_content_types(configured)


def _validate_template(template: str, *, field_name: str) -> str:
    normalized = (template or "").strip()
    if not normalized:
        raise ValidationError(f"{field_name}不能为空")

    formatter = Formatter()
    placeholders = {field_name for _, field_name, _, _ in formatter.parse(normalized) if field_name}
    invalid = sorted(placeholders - TEMPLATE_ALLOWED_KEYS)
    if invalid:
        raise ValidationError(
            f"{field_name}包含不支持的占位符：{', '.join(invalid)}。可用占位符：{', '.join(sorted(TEMPLATE_ALLOWED_KEYS))}"
        )
    return normalized


def _render_template(template: str, context: dict[str, str]) -> str:
    try:
        return template.format_map(context)
    except KeyError as exc:  # pragma: no cover - protected by _validate_template
        raise ValidationError(f"模板占位符缺失：{exc.args[0]}") from exc


def _normalize_email(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise ValidationError("请输入有效的邮箱地址")
    return normalized


def _default_config_payload() -> dict[str, object]:
    settings = get_settings()
    return {
        "enabled": False,
        "smtp_auth_mode": _normalize_smtp_auth_mode(settings.subscription_smtp_auth_mode),
        "smtp_host": settings.subscription_smtp_host.strip(),
        "smtp_port": int(settings.subscription_smtp_port or 587),
        "smtp_username": settings.subscription_smtp_username.strip(),
        "smtp_password": settings.subscription_smtp_password.strip(),
        "smtp_oauth_tenant": settings.subscription_smtp_oauth_tenant.strip() or "common",
        "smtp_oauth_client_id": settings.subscription_smtp_oauth_client_id.strip(),
        "smtp_oauth_client_secret": settings.subscription_smtp_oauth_client_secret.strip(),
        "smtp_oauth_refresh_token": settings.subscription_smtp_oauth_refresh_token.strip(),
        "smtp_from_email": settings.subscription_smtp_from_email.strip(),
        "smtp_from_name": settings.subscription_smtp_from_name.strip(),
        "smtp_reply_to": settings.subscription_smtp_reply_to.strip(),
        "smtp_use_tls": bool(settings.subscription_smtp_use_tls),
        "smtp_use_ssl": bool(settings.subscription_smtp_use_ssl),
        "smtp_test_passed": False,
        "smtp_tested_at": None,
        "allowed_content_types": list(DEFAULT_ALLOWED_CONTENT_TYPES),
        "mail_subject_template": DEFAULT_SUBJECT_TEMPLATE,
        "mail_body_template": DEFAULT_BODY_TEMPLATE,
    }


def get_subscription_config_orm(session: Session) -> ContentSubscriptionConfig:
    config = session.scalars(
        select(ContentSubscriptionConfig).order_by(ContentSubscriptionConfig.created_at.asc())
    ).first()
    if config is not None:
        return config
    config = ContentSubscriptionConfig(**_default_config_payload())
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def _active_subscriber_count(session: Session) -> int:
    return (
        session.scalar(select(func.count()).select_from(ContentSubscriber).where(ContentSubscriber.is_active.is_(True)))
        or 0
    )


def get_subscription_admin_config(session: Session) -> ContentSubscriptionConfigAdminRead:
    config = get_subscription_config_orm(session)
    return ContentSubscriptionConfigAdminRead.model_validate(config).model_copy(
        update={"subscriber_count": _active_subscriber_count(session)}
    )


def update_subscription_admin_config(
    session: Session,
    payload: ContentSubscriptionConfigAdminUpdate,
) -> ContentSubscriptionConfigAdminRead:
    config = get_subscription_config_orm(session)
    updates = payload.model_dump(exclude_unset=True)
    smtp_changed = _smtp_settings_will_change(config, updates)
    _apply_subscription_updates(config, updates)
    if smtp_changed:
        config.smtp_test_passed = False
        config.smtp_tested_at = None

    session.commit()
    session.refresh(config)
    return get_subscription_admin_config(session)


def subscription_enabled(session: Session) -> bool:
    config = get_subscription_config_orm(session)
    return bool(config.enabled and config.smtp_test_passed)


def create_or_update_public_subscription(
    session: Session,
    payload: ContentSubscriptionPublicCreate,
    *,
    current_user: SiteUser | None = None,
) -> ContentSubscriptionPublicRead:
    config = get_subscription_config_orm(session)
    if not (config.enabled and config.smtp_test_passed):
        raise ValidationError("订阅功能尚未开启")

    email = _normalize_email(payload.email)
    content_types = _normalize_content_types(payload.content_types)
    allowed_content_types = set(_config_allowed_content_types(config))
    disallowed = [item for item in content_types if item not in allowed_content_types]
    if disallowed:
        raise ValidationError(f"以下订阅类型暂未开放：{', '.join(disallowed)}")
    if not _smtp_ready(config):
        raise _smtp_incomplete_validation_error(config)

    subscriber = session.scalars(select(ContentSubscriber).where(ContentSubscriber.email == email)).first()
    if subscriber is None:
        subscriber = ContentSubscriber(
            email=email,
            initiator_site_user_id=current_user.id if current_user is not None else None,
            content_types=content_types,
            is_active=True,
        )
        session.add(subscriber)
    else:
        if current_user is not None:
            subscriber.initiator_site_user_id = current_user.id
        subscriber.content_types = content_types
        subscriber.is_active = True

    settings = get_settings()
    site = site_config_repo.find_site_profile(session)
    site_name = (
        (site.title if site is not None else "").strip()
        or (site.name if site is not None else "").strip()
        or "Aerisun"
    )
    site_url = (settings.site_url or "https://example.com").rstrip("/")
    welcome_message = _build_subscription_welcome_message(
        config=config,
        recipient=email,
        content_types=content_types,
        site_name=site_name,
        site_url=site_url,
    )

    try:
        _send_email(config=config, message=welcome_message)
    except (smtplib.SMTPException, httpx.HTTPError, OSError) as exc:
        logger.warning("Subscription welcome email failed for %s", email, exc_info=exc)
        session.rollback()
        raise ValidationError("订阅确认邮件发送失败，请确认邮箱地址后重试") from exc

    session.commit()
    session.refresh(subscriber)
    return ContentSubscriptionPublicRead(
        email=subscriber.email,
        content_types=list(subscriber.content_types or []),
        subscribed=bool(subscriber.is_active),
    )


def get_public_subscription_for_email(
    session: Session,
    *,
    email: str,
) -> ContentSubscriptionPublicStatusRead:
    normalized_email = _normalize_email(email)
    subscriber = session.scalars(
        select(ContentSubscriber).where(ContentSubscriber.email == normalized_email)
    ).first()
    if subscriber is None:
        return ContentSubscriptionPublicStatusRead(
            email=normalized_email,
            content_types=[],
            subscribed=False,
        )

    return ContentSubscriptionPublicStatusRead(
        email=subscriber.email,
        content_types=list(subscriber.content_types or []),
        subscribed=bool(subscriber.is_active),
    )


def unsubscribe_public_subscription(
    session: Session,
    *,
    email: str,
) -> ContentSubscriptionPublicUnsubscribeResult:
    normalized_email = _normalize_email(email)
    subscriber = session.scalars(
        select(ContentSubscriber).where(ContentSubscriber.email == normalized_email)
    ).first()
    if subscriber is not None and subscriber.is_active:
        subscriber.is_active = False
        session.commit()

    return ContentSubscriptionPublicUnsubscribeResult(
        email=normalized_email,
        unsubscribed=True,
    )


def _smtp_ready(config: ContentSubscriptionConfig) -> bool:
    base_ready = all(
        [
            config.smtp_host.strip(),
            config.smtp_port,
            config.smtp_from_email.strip(),
        ]
    )
    if not base_ready:
        return False
    if _smtp_auth_mode(config) == SMTP_AUTH_MODE_MICROSOFT_OAUTH2:
        return all(
            [
                config.smtp_oauth_tenant.strip(),
                config.smtp_oauth_client_id.strip(),
                config.smtp_oauth_client_secret.strip(),
                config.smtp_oauth_refresh_token.strip(),
            ]
        )
    return True


def _smtp_auth_mode(config: ContentSubscriptionConfig) -> str:
    return _normalize_smtp_auth_mode(config.smtp_auth_mode)


def _normalize_update_value(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _smtp_settings_will_change(config: ContentSubscriptionConfig, updates: dict[str, object]) -> bool:
    for key in SMTP_SETTING_KEYS:
        if key not in updates:
            continue
        if getattr(config, key) != _normalize_update_value(updates[key]):
            return True
    return False


def _apply_subscription_updates(
    config: ContentSubscriptionConfig,
    updates: dict[str, object],
) -> ContentSubscriptionConfig:
    if "smtp_auth_mode" in updates:
        updates["smtp_auth_mode"] = _normalize_smtp_auth_mode(str(updates.get("smtp_auth_mode") or ""))
    if "allowed_content_types" in updates:
        raw_content_types = updates.get("allowed_content_types")
        if not isinstance(raw_content_types, list):
            raise ValidationError("订阅内容配置格式错误")
        updates["allowed_content_types"] = _normalize_allowed_content_types(raw_content_types)
    if "mail_subject_template" in updates:
        updates["mail_subject_template"] = _validate_template(
            str(updates.get("mail_subject_template") or ""),
            field_name="邮件标题模板",
        )
    if "mail_body_template" in updates:
        updates["mail_body_template"] = _validate_template(
            str(updates.get("mail_body_template") or ""),
            field_name="邮件正文模板",
        )
    next_tls = bool(updates.get("smtp_use_tls", config.smtp_use_tls))
    next_ssl = bool(updates.get("smtp_use_ssl", config.smtp_use_ssl))
    if next_tls and next_ssl:
        raise ValidationError("TLS 和 SSL 不能同时开启")

    for key, value in updates.items():
        setattr(config, key, _normalize_update_value(value))
    return config


def _smtp_test_recipient() -> str:
    return SUBSCRIPTION_TEST_RECIPIENT


def _smtp_login_identity(config: ContentSubscriptionConfig) -> str:
    if _smtp_auth_mode(config) == SMTP_AUTH_MODE_MICROSOFT_OAUTH2:
        return config.smtp_username.strip() or config.smtp_from_email.strip()
    return config.smtp_username.strip()


def _microsoft_token_endpoint(config: ContentSubscriptionConfig) -> str:
    tenant = config.smtp_oauth_tenant.strip() or "common"
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


def _fetch_microsoft_smtp_access_token(config: ContentSubscriptionConfig) -> str:
    try:
        response = httpx.post(
            _microsoft_token_endpoint(config),
            data={
                "client_id": config.smtp_oauth_client_id.strip(),
                "client_secret": config.smtp_oauth_client_secret.strip(),
                "refresh_token": config.smtp_oauth_refresh_token.strip(),
                "grant_type": "refresh_token",
                "scope": MICROSOFT_SMTP_SCOPE,
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Microsoft SMTP OAuth2 token request failed", exc_info=exc)
        raise ValidationError(
            "Microsoft OAuth2 令牌获取失败，请检查租户、Client ID、Client Secret 和 Refresh Token"
        ) from exc

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.is_error:
        logger.warning(
            "Microsoft SMTP OAuth2 token request failed with status %s: %s",
            response.status_code,
            payload if payload else response.text[:500],
        )
        raise ValidationError("Microsoft OAuth2 令牌获取失败，请检查租户、Client ID、Client Secret 和 Refresh Token")

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        logger.warning("Microsoft SMTP OAuth2 token response missing access_token: %s", payload)
        raise ValidationError("Microsoft OAuth2 令牌获取失败，请检查租户、Client ID、Client Secret 和 Refresh Token")

    refreshed_refresh_token = str(payload.get("refresh_token") or "").strip()
    if refreshed_refresh_token and refreshed_refresh_token != config.smtp_oauth_refresh_token:
        config.smtp_oauth_refresh_token = refreshed_refresh_token

    return access_token


def _smtp_login_validation_error(config: ContentSubscriptionConfig) -> ValidationError:
    if _smtp_auth_mode(config) == SMTP_AUTH_MODE_MICROSOFT_OAUTH2:
        return ValidationError(
            "请检查 SMTP 主机、端口、Microsoft OAuth2 租户、Client ID、Client Secret 和 Refresh Token"
        )
    return ValidationError("请检查 SMTP 主机、端口、用户名、密码和加密方式是否正确")


def _smtp_incomplete_validation_error(config: ContentSubscriptionConfig) -> ValidationError:
    if _smtp_auth_mode(config) == SMTP_AUTH_MODE_MICROSOFT_OAUTH2:
        return ValidationError(
            "请先填写 SMTP 主机、端口、发件邮箱，以及 Microsoft OAuth2 的租户、"
            "Client ID、Client Secret 和 Refresh Token"
        )
    return ValidationError("请先填写 SMTP 主机、端口和发件邮箱")


def _strip_html(value: str) -> str:
    text = value.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    inside_tag = False
    chars: list[str] = []
    for char in text:
        if char == "<":
            inside_tag = True
            continue
        if char == ">":
            inside_tag = False
            continue
        if not inside_tag:
            chars.append(char)
    return " ".join("".join(chars).split())


def _ensure_notification_records(session: Session, site_url: str) -> int:
    existing = {
        (item.content_type, item.content_slug): item for item in session.scalars(select(ContentNotification)).all()
    }
    created = 0
    settings_url = site_url.rstrip("/")

    for content_type, model in CONTENT_MODELS.items():
        definition = get_feed_definition(content_type)
        items = session.scalars(select(model).where(model.status == "published", model.visibility == "public")).all()
        for item in items:
            key = (content_type, item.slug)
            if key in existing:
                continue
            published_at = item.published_at or item.created_at
            session.add(
                ContentNotification(
                    content_type=content_type,
                    content_slug=item.slug,
                    content_title=item.title,
                    content_summary=item.summary or _strip_html(item.body),
                    content_url=f"{settings_url}{definition.item_path_template.format(slug=item.slug)}",
                    published_at=published_at,
                )
            )
            created += 1

    if created:
        session.commit()
    return created


def _record_notification_deliveries(
    session: Session,
    *,
    notification: ContentNotification,
    recipients: list[str],
    status: str,
    sent_at: datetime | None = None,
    error_message: str | None = None,
) -> None:
    for email in recipients:
        session.add(
            ContentNotificationDelivery(
                notification_id=notification.id,
                subscriber_email=email,
                content_type=notification.content_type,
                content_slug=notification.content_slug,
                content_title=notification.content_title,
                content_url=notification.content_url,
                status=status,
                error_message=error_message,
                sent_at=sent_at,
            )
        )


def _recipient_emails_for_notification(
    session: Session,
    *,
    config: ContentSubscriptionConfig,
    content_type: str,
) -> list[str]:
    if content_type not in set(_config_allowed_content_types(config)):
        return []

    subscribers = session.scalars(select(ContentSubscriber).where(ContentSubscriber.is_active.is_(True))).all()
    emails: list[str] = []
    for subscriber in subscribers:
        content_types = _normalize_content_types(list(subscriber.content_types or []))
        if content_type in content_types:
            emails.append(subscriber.email)
    return sorted(set(emails))


def list_admin_subscribers(
    session: Session,
    *,
    mode: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ContentSubscriberAdminRead], int]:
    filters = [ContentSubscriber.is_active.is_(True)]

    normalized_search = " ".join((search or "").strip().split())
    initiator_binding_exists = exists(
        select(SiteUserOAuthAccount.id).where(
            SiteUserOAuthAccount.site_user_id == ContentSubscriber.initiator_site_user_id
        )
    )
    initiator_exists = ContentSubscriber.initiator_site_user_id.is_not(None)
    if mode == "email":
        filters.append(initiator_exists)
        filters.append(~initiator_binding_exists)
    elif mode == "binding":
        filters.append(initiator_binding_exists)
    elif mode == "subscriber":
        filters.append(initiator_exists)
    elif mode != "all":
        raise ValidationError("不支持的订阅者筛选方式")

    stmt = (
        select(ContentSubscriber)
        .where(*filters)
        .order_by(ContentSubscriber.updated_at.desc(), ContentSubscriber.created_at.desc())
    )
    subscribers = list(session.scalars(stmt).all())

    initiator_ids = [item.initiator_site_user_id for item in subscribers if item.initiator_site_user_id]
    users = (
        list(session.scalars(select(SiteUser).where(SiteUser.id.in_(initiator_ids))).all())
        if initiator_ids
        else []
    )
    user_by_id = {user.id: user for user in users}
    user_ids = [user.id for user in users]
    oauth_rows = (
        list(session.scalars(select(SiteUserOAuthAccount).where(SiteUserOAuthAccount.site_user_id.in_(user_ids))).all())
        if user_ids
        else []
    )
    oauth_map: dict[str, list[str]] = {}
    for row in oauth_rows:
        oauth_map.setdefault(row.site_user_id, []).append(row.provider)

    emails = [item.email for item in subscribers]
    stats_rows = session.execute(
        select(
            ContentNotificationDelivery.subscriber_email,
            func.count(ContentNotificationDelivery.id),
            func.max(ContentNotificationDelivery.sent_at),
        )
        .where(
            ContentNotificationDelivery.subscriber_email.in_(emails),
            ContentNotificationDelivery.status == "sent",
        )
        .group_by(ContentNotificationDelivery.subscriber_email)
    ).all()
    delivery_stats = {
        email: {
            "sent_count": int(count or 0),
            "last_sent_at": last_sent_at,
        }
        for email, count, last_sent_at in stats_rows
    }

    items: list[ContentSubscriberAdminRead] = []
    for subscriber in subscribers:
        matched_user = (
            user_by_id.get(subscriber.initiator_site_user_id)
            if subscriber.initiator_site_user_id
            else None
        )
        providers = sorted(set(oauth_map.get(matched_user.id, []))) if matched_user else []
        auth_mode = "unknown"
        if matched_user is not None:
            auth_mode = "binding" if providers else "email"
        stats = delivery_stats.get(subscriber.email, {"sent_count": 0, "last_sent_at": None})
        items.append(
            ContentSubscriberAdminRead(
                email=subscriber.email,
                is_active=bool(subscriber.is_active),
                content_types=list(subscriber.content_types or []),
                auth_mode=auth_mode,
                initiator_email=matched_user.email if matched_user else None,
                display_name=matched_user.display_name if matched_user else None,
                avatar_url=matched_user.avatar_url if matched_user else None,
                primary_auth_provider=matched_user.primary_auth_provider if matched_user else None,
                oauth_providers=providers,
                sent_count=int(stats["sent_count"]),
                last_sent_at=stats["last_sent_at"],
                created_at=subscriber.created_at,
                updated_at=subscriber.updated_at,
            )
        )
    if normalized_search:
        pattern = normalized_search.casefold()
        items = [
            item
            for item in items
            if pattern in item.email.casefold()
            or pattern in (item.initiator_email or "").casefold()
            or pattern in (item.display_name or "").casefold()
        ]

    total = len(items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return items[start:end], total


def list_subscriber_delivery_history(
    session: Session,
    *,
    email: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ContentNotificationDeliveryAdminRead], int]:
    normalized_email = _normalize_email(email)
    stmt = (
        select(ContentNotificationDelivery)
        .where(ContentNotificationDelivery.subscriber_email == normalized_email)
        .order_by(ContentNotificationDelivery.created_at.desc())
    )
    total = int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return [ContentNotificationDeliveryAdminRead.model_validate(row) for row in rows], total


def _build_email_message(
    *,
    config: ContentSubscriptionConfig,
    notification: ContentNotification,
    recipients: list[str],
    site_name: str,
    site_url: str,
) -> EmailMessage:
    msg = EmailMessage()
    from_name = config.smtp_from_name.strip() or site_name
    feed_path = get_feed_definition(notification.content_type).feed_path
    content_label = CONTENT_TYPE_LABELS.get(notification.content_type, notification.content_type)
    summary = (notification.content_summary or "").strip()
    context = {
        "site_name": site_name,
        "content_type": notification.content_type,
        "content_type_label": content_label,
        "content_title": notification.content_title,
        "content_summary": summary,
        "content_url": notification.content_url,
        "feed_url": f"{site_url}{feed_path}",
    }
    subject_template = _validate_template(
        config.mail_subject_template or DEFAULT_SUBJECT_TEMPLATE,
        field_name="邮件标题模板",
    )
    body_template = _validate_template(
        config.mail_body_template or DEFAULT_BODY_TEMPLATE,
        field_name="邮件正文模板",
    )

    msg["Subject"] = _render_template(subject_template, context)
    msg["From"] = f"{from_name} <{config.smtp_from_email}>"
    msg["To"] = config.smtp_from_email
    msg["Bcc"] = ", ".join(recipients)
    if config.smtp_reply_to.strip():
        msg["Reply-To"] = config.smtp_reply_to.strip()

    msg.set_content(_render_template(body_template, context))
    return msg


def _build_subscription_welcome_message(
    *,
    config: ContentSubscriptionConfig,
    recipient: str,
    content_types: list[str],
    site_name: str,
    site_url: str,
) -> EmailMessage:
    msg = EmailMessage()
    from_name = config.smtp_from_name.strip() or site_name
    labels = [CONTENT_TYPE_LABELS.get(item, item) for item in content_types]
    selected_lines = "\n".join(f"- {label}" for label in labels) if labels else "- 全部"

    msg["Subject"] = f"[{site_name}] 订阅成功"
    msg["From"] = f"{from_name} <{config.smtp_from_email}>"
    msg["To"] = recipient
    if config.smtp_reply_to.strip():
        msg["Reply-To"] = config.smtp_reply_to.strip()

    msg.set_content(
        "\n".join(
            [
                f"你好，你已成功订阅 {site_name} 的内容更新。",
                "",
                "当前订阅类型：",
                selected_lines,
                "",
                f"站点地址：{site_url}",
                "",
                "如果这不是你的操作，请忽略此邮件或在站点中取消订阅。",
            ]
        )
    )
    return msg


def _send_email(
    *,
    config: ContentSubscriptionConfig,
    message: EmailMessage,
) -> None:
    username = _smtp_login_identity(config)
    password = config.smtp_password.strip()

    def _authenticate(server: smtplib.SMTP) -> None:
        if _smtp_auth_mode(config) == SMTP_AUTH_MODE_MICROSOFT_OAUTH2:
            access_token = _fetch_microsoft_smtp_access_token(config)
            auth_string = base64.b64encode(
                f"user={username}\x01auth=Bearer {access_token}\x01\x01".encode()
            ).decode("ascii")
            code, response = server.docmd("AUTH", f"XOAUTH2 {auth_string}")
            if code != 235:
                raise smtplib.SMTPAuthenticationError(code, response)
            return
        if username:
            server.login(username, password)

    if config.smtp_use_ssl:
        with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=20) as server:
            _authenticate(server)
            server.send_message(message)
        return

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as server:
        server.ehlo()
        if config.smtp_use_tls:
            server.starttls()
            server.ehlo()
        _authenticate(server)
        server.send_message(message)


def send_subscription_test_email(
    session: Session,
    payload: ContentSubscriptionConfigAdminUpdate,
    settings: Settings | None = None,
) -> ContentSubscriptionTestResult:
    current = get_subscription_config_orm(session)
    test_config = ContentSubscriptionConfig(
        enabled=current.enabled,
        smtp_auth_mode=current.smtp_auth_mode,
        smtp_host=current.smtp_host,
        smtp_port=current.smtp_port,
        smtp_username=current.smtp_username,
        smtp_password=current.smtp_password,
        smtp_oauth_tenant=current.smtp_oauth_tenant,
        smtp_oauth_client_id=current.smtp_oauth_client_id,
        smtp_oauth_client_secret=current.smtp_oauth_client_secret,
        smtp_oauth_refresh_token=current.smtp_oauth_refresh_token,
        smtp_from_email=current.smtp_from_email,
        smtp_from_name=current.smtp_from_name,
        smtp_reply_to=current.smtp_reply_to,
        smtp_use_tls=current.smtp_use_tls,
        smtp_use_ssl=current.smtp_use_ssl,
        allowed_content_types=list(current.allowed_content_types or DEFAULT_ALLOWED_CONTENT_TYPES),
        mail_subject_template=current.mail_subject_template or DEFAULT_SUBJECT_TEMPLATE,
        mail_body_template=current.mail_body_template or DEFAULT_BODY_TEMPLATE,
    )
    updates = payload.model_dump(exclude_unset=True, exclude={"enabled"})
    _apply_subscription_updates(test_config, updates)

    if not _smtp_ready(test_config):
        raise _smtp_incomplete_validation_error(test_config)

    username = _smtp_login_identity(test_config)
    password = test_config.smtp_password.strip()
    if _smtp_auth_mode(test_config) == SMTP_AUTH_MODE_PASSWORD and username and not password:
        raise ValidationError("填写了 SMTP 用户名后，还需要填写对应的密码或授权码")

    active_settings = settings or get_settings()
    site = site_config_repo.find_site_profile(session)
    site_name = (
        (site.title if site is not None else "").strip() or (site.name if site is not None else "").strip() or "Aerisun"
    )
    recipient = _smtp_test_recipient()

    message = EmailMessage()
    from_name = test_config.smtp_from_name.strip() or site_name
    message["Subject"] = f"[{site_name}] SMTP Test"
    message["From"] = f"{from_name} <{test_config.smtp_from_email}>"
    message["To"] = recipient
    if test_config.smtp_reply_to.strip():
        message["Reply-To"] = test_config.smtp_reply_to.strip()
    message["Message-ID"] = f"<subscription-test-{uuid4().hex}@aerisun.local>"
    message.set_content(
        "\n".join(
            [
                "This is a test email from Aerisun.",
                f"Site: {site_name}",
                f"URL: {(active_settings.site_url or 'https://example.com').rstrip('/')}",
                "",
                "If you received this email, the current SMTP configuration can connect and send mail.",
            ]
        )
    )

    try:
        _send_email(config=test_config, message=message)
    except (smtplib.SMTPException, httpx.HTTPError) as exc:
        logger.warning("Subscription SMTP test email failed", exc_info=exc)
        raise _smtp_login_validation_error(test_config) from exc
    except OSError as exc:
        logger.warning("Subscription SMTP test email failed", exc_info=exc)
        raise _smtp_login_validation_error(test_config) from exc

    # Persist the tested SMTP settings as available on success.
    _apply_subscription_updates(current, updates)
    current.smtp_test_passed = True
    current.smtp_tested_at = utcnow()
    session.commit()
    session.refresh(current)

    return ContentSubscriptionTestResult(recipient=recipient)


def dispatch_content_subscription_notifications(settings: Settings | None = None) -> dict[str, int]:
    active_settings = settings or get_settings()
    session_factory = get_session_factory()
    summary = {"created": 0, "sent": 0, "skipped": 0}
    site_url = (active_settings.site_url or "https://example.com").rstrip("/")

    with session_factory() as session:
        config = get_subscription_config_orm(session)
        summary["created"] = _ensure_notification_records(session, site_url)

        pending = session.scalars(
            select(ContentNotification)
            .where(ContentNotification.delivered_at.is_(None))
            .order_by(ContentNotification.published_at.asc().nullsfirst(), ContentNotification.created_at.asc())
        ).all()

        if not pending:
            return summary

        if not config.enabled:
            summary["skipped"] += len(pending)
            return summary

        if not config.smtp_test_passed:
            logger.warning("Content subscription SMTP config is not verified by test send")
            return summary

        if not _smtp_ready(config):
            logger.warning("Content subscription SMTP config is incomplete; leaving notifications pending")
            return summary

        site = site_config_repo.find_site_profile(session)
        site_name = (
            (site.title if site is not None else "").strip()
            or (site.name if site is not None else "").strip()
            or "Aerisun"
        )
        for item in pending:
            recipients = _recipient_emails_for_notification(
                session,
                config=config,
                content_type=item.content_type,
            )
            if not recipients:
                item.delivered_at = utcnow()
                session.commit()
                summary["skipped"] += 1
                continue

            message = _build_email_message(
                config=config,
                notification=item,
                recipients=recipients,
                site_name=site_name,
                site_url=site_url,
            )
            try:
                _send_email(config=config, message=message)
            except Exception as exc:
                logger.exception(
                    "Failed to send content subscription email for %s/%s",
                    item.content_type,
                    item.content_slug,
                )
                _record_notification_deliveries(
                    session,
                    notification=item,
                    recipients=recipients,
                    status="failed",
                    error_message=str(exc)[:1000],
                )
                session.commit()
                continue

            delivered_at = utcnow()
            _record_notification_deliveries(
                session,
                notification=item,
                recipients=recipients,
                status="sent",
                sent_at=delivered_at,
            )
            item.delivered_at = delivered_at
            session.commit()
            summary["sent"] += 1

    return summary
