from __future__ import annotations

from typing import Any
from uuid import uuid4

from aerisun.domain.automation.models import AutomationEvent
from aerisun.domain.automation.service import emit_event


def _emit(
    session,
    *,
    event_type: str,
    target_type: str,
    target_id: str,
    payload: dict[str, Any],
) -> None:
    event = AutomationEvent(
        event_type=event_type,
        event_id=uuid4().hex,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
    )
    emit_event(session, event)


def emit_comment_pending(
    session,
    *,
    comment_id: str,
    content_type: str,
    content_slug: str,
    author_name: str,
    body_preview: str,
) -> None:
    _emit(
        session,
        event_type="comment.pending",
        target_type="comment",
        target_id=comment_id,
        payload={
            "comment_id": comment_id,
            "content_type": content_type,
            "content_slug": content_slug,
            "author_name": author_name,
            "body_preview": body_preview,
        },
    )


def emit_guestbook_pending(
    session,
    *,
    entry_id: str,
    author_name: str,
    body_preview: str,
) -> None:
    _emit(
        session,
        event_type="guestbook.pending",
        target_type="guestbook",
        target_id=entry_id,
        payload={
            "entry_id": entry_id,
            "author_name": author_name,
            "body_preview": body_preview,
        },
    )


def emit_comment_moderated(session, *, comment_id: str, action: str, reason: str | None = None) -> None:
    _emit(
        session,
        event_type=f"comment.{action}",
        target_type="comment",
        target_id=comment_id,
        payload={"comment_id": comment_id, "action": action, "reason": reason},
    )


def emit_guestbook_moderated(session, *, entry_id: str, action: str, reason: str | None = None) -> None:
    _emit(
        session,
        event_type=f"guestbook.{action}",
        target_type="guestbook",
        target_id=entry_id,
        payload={"entry_id": entry_id, "action": action, "reason": reason},
    )


def emit_content_created(
    session,
    *,
    content_type: str,
    item_id: str,
    slug: str,
    title: str,
    status: str | None,
    visibility: str | None,
) -> None:
    _emit(
        session,
        event_type="content.created",
        target_type="content",
        target_id=item_id,
        payload={
            "content_type": content_type,
            "item_id": item_id,
            "content_id": item_id,
            "slug": slug,
            "title": title,
            "status": status,
            "visibility": visibility,
        },
    )


def emit_content_updated(
    session,
    *,
    content_type: str,
    item_id: str,
    slug: str,
    title: str,
    status: str | None,
    visibility: str | None,
    changed_fields: list[str],
) -> None:
    _emit(
        session,
        event_type="content.updated",
        target_type="content",
        target_id=item_id,
        payload={
            "content_type": content_type,
            "item_id": item_id,
            "content_id": item_id,
            "slug": slug,
            "title": title,
            "status": status,
            "visibility": visibility,
            "changed_fields": changed_fields,
        },
    )


def emit_content_deleted(
    session,
    *,
    content_type: str,
    item_id: str,
    slug: str,
    title: str,
) -> None:
    _emit(
        session,
        event_type="content.deleted",
        target_type="content",
        target_id=item_id,
        payload={
            "content_type": content_type,
            "item_id": item_id,
            "content_id": item_id,
            "slug": slug,
            "title": title,
        },
    )


def emit_content_bulk_deleted(
    session,
    *,
    content_type: str,
    ids: list[str],
    affected: int,
) -> None:
    _emit(
        session,
        event_type="content.bulk_deleted",
        target_type="content_batch",
        target_id=str(ids[0] if ids else "content-batch"),
        payload={
            "content_type": content_type,
            "item_ids": ids,
            "affected": affected,
        },
    )


def emit_content_status_changed(
    session,
    *,
    content_type: str,
    ids: list[str],
    status: str,
    visibility: str | None,
    affected: int,
) -> None:
    _emit(
        session,
        event_type="content.status_changed",
        target_type="content_batch",
        target_id=str(ids[0] if ids else "content-batch"),
        payload={
            "content_type": content_type,
            "item_ids": ids,
            "status": status,
            "visibility": visibility,
            "affected": affected,
        },
    )


def emit_content_published(
    session,
    *,
    content_type: str,
    item_id: str,
    slug: str,
    title: str,
) -> None:
    _emit(
        session,
        event_type="content.published",
        target_type="content",
        target_id=item_id,
        payload={
            "content_type": content_type,
            "item_id": item_id,
            "content_id": item_id,
            "slug": slug,
            "title": title,
        },
    )


def emit_content_archived(
    session,
    *,
    content_type: str,
    item_id: str,
    slug: str,
    title: str,
) -> None:
    _emit(
        session,
        event_type="content.archived",
        target_type="content",
        target_id=item_id,
        payload={
            "content_type": content_type,
            "item_id": item_id,
            "content_id": item_id,
            "slug": slug,
            "title": title,
        },
    )


def emit_content_visibility_changed(
    session,
    *,
    content_type: str,
    item_id: str,
    slug: str,
    title: str,
    visibility: str | None,
) -> None:
    _emit(
        session,
        event_type="content.visibility_changed",
        target_type="content",
        target_id=item_id,
        payload={
            "content_type": content_type,
            "item_id": item_id,
            "content_id": item_id,
            "slug": slug,
            "title": title,
            "visibility": visibility,
        },
    )


def emit_subscription_config_updated(
    session,
    *,
    changed_fields: list[str],
    enabled: bool,
    smtp_test_passed: bool,
    allowed_content_types: list[str],
) -> None:
    _emit(
        session,
        event_type="subscription.config_updated",
        target_type="subscription_config",
        target_id="content-subscription-config",
        payload={
            "changed_fields": changed_fields,
            "enabled": enabled,
            "smtp_test_passed": smtp_test_passed,
            "allowed_content_types": allowed_content_types,
        },
    )


def emit_subscription_created(
    session,
    *,
    email: str,
    content_types: list[str],
    initiator_site_user_id: str | None,
) -> None:
    _emit(
        session,
        event_type="subscription.created",
        target_type="subscription",
        target_id=email,
        payload={
            "email": email,
            "content_types": content_types,
            "initiator_site_user_id": initiator_site_user_id,
        },
    )


def emit_subscription_unsubscribed(session, *, email: str) -> None:
    _emit(
        session,
        event_type="subscription.unsubscribed",
        target_type="subscription",
        target_id=email,
        payload={"email": email},
    )


def emit_subscription_notification_sent(
    session,
    *,
    notification_id: str,
    content_type: str,
    content_slug: str,
    recipient_count: int,
) -> None:
    _emit(
        session,
        event_type="subscription.notification.sent",
        target_type="subscription_notification",
        target_id=notification_id,
        payload={
            "notification_id": notification_id,
            "content_type": content_type,
            "content_slug": content_slug,
            "recipient_count": recipient_count,
        },
    )


def emit_subscription_notification_failed(
    session,
    *,
    notification_id: str,
    content_type: str,
    content_slug: str,
    recipient_count: int,
    error: str,
) -> None:
    _emit(
        session,
        event_type="subscription.notification.failed",
        target_type="subscription_notification",
        target_id=notification_id,
        payload={
            "notification_id": notification_id,
            "content_type": content_type,
            "content_slug": content_slug,
            "recipient_count": recipient_count,
            "error": error,
        },
    )


def emit_backup_config_updated(
    session,
    *,
    config_id: str,
    enabled: bool,
    paused: bool,
    transport_mode: str,
    interval_minutes: int,
) -> None:
    _emit(
        session,
        event_type="backup.config_updated",
        target_type="backup_config",
        target_id=config_id,
        payload={
            "config_id": config_id,
            "enabled": enabled,
            "paused": paused,
            "transport_mode": transport_mode,
            "interval_minutes": interval_minutes,
        },
    )


def emit_backup_sync_triggered(
    session,
    *,
    queue_item_id: str,
    trigger_kind: str,
    transport: str,
) -> None:
    _emit(
        session,
        event_type="backup.sync.triggered",
        target_type="backup_sync",
        target_id=queue_item_id,
        payload={
            "queue_item_id": queue_item_id,
            "trigger_kind": trigger_kind,
            "transport": transport,
        },
    )


def emit_backup_sync_started(
    session,
    *,
    run_id: str,
    queue_item_id: str | None,
    trigger_kind: str | None,
    transport: str | None,
) -> None:
    _emit(
        session,
        event_type="backup.sync.started",
        target_type="backup_sync_run",
        target_id=run_id,
        payload={
            "run_id": run_id,
            "queue_item_id": queue_item_id,
            "trigger_kind": trigger_kind,
            "transport": transport,
        },
    )


def emit_backup_sync_completed(
    session,
    *,
    run_id: str,
    queue_item_id: str | None,
    commit_id: str,
    stats: dict[str, Any],
) -> None:
    _emit(
        session,
        event_type="backup.sync.completed",
        target_type="backup_sync_run",
        target_id=run_id,
        payload={
            "run_id": run_id,
            "queue_item_id": queue_item_id,
            "commit_id": commit_id,
            "stats": stats,
        },
    )


def emit_backup_sync_failed(
    session,
    *,
    run_id: str,
    queue_item_id: str | None,
    error: str,
    retry_count: int,
) -> None:
    _emit(
        session,
        event_type="backup.sync.failed",
        target_type="backup_sync_run",
        target_id=run_id,
        payload={
            "run_id": run_id,
            "queue_item_id": queue_item_id,
            "error": error,
            "retry_count": retry_count,
        },
    )


def emit_backup_sync_retried(
    session,
    *,
    run_id: str,
    queue_item_id: str,
    retry_count: int,
) -> None:
    _emit(
        session,
        event_type="backup.sync.retried",
        target_type="backup_sync_run",
        target_id=run_id,
        payload={
            "run_id": run_id,
            "queue_item_id": queue_item_id,
            "retry_count": retry_count,
        },
    )


def emit_friend_site_checked(
    session,
    *,
    friend_id: str,
    friend_name: str,
    previous_status: str,
    status: str,
    error: str | None = None,
) -> None:
    _emit(
        session,
        event_type="friend.site_checked",
        target_type="friend",
        target_id=friend_id,
        payload={
            "friend_id": friend_id,
            "friend_name": friend_name,
            "previous_status": previous_status,
            "status": status,
            "error": error,
        },
    )
    if previous_status != status:
        _emit(
            session,
            event_type="friend.site_recovered" if status == "active" else "friend.site_lost",
            target_type="friend",
            target_id=friend_id,
            payload={
                "friend_id": friend_id,
                "friend_name": friend_name,
                "previous_status": previous_status,
                "status": status,
                "error": error,
            },
        )


def emit_friend_feed_checked(
    session,
    *,
    source_id: str,
    friend_id: str,
    friend_name: str,
    status: str,
    inserted: int,
    feed_url_updated: bool,
    error: str | None = None,
) -> None:
    _emit(
        session,
        event_type="friend.feed_checked",
        target_type="friend_feed_source",
        target_id=source_id,
        payload={
            "source_id": source_id,
            "friend_id": friend_id,
            "friend_name": friend_name,
            "status": status,
            "inserted": inserted,
            "feed_url_updated": feed_url_updated,
            "error": error,
        },
    )
    if error:
        _emit(
            session,
            event_type="friend.feed_error",
            target_type="friend_feed_source",
            target_id=source_id,
            payload={
                "source_id": source_id,
                "friend_id": friend_id,
                "friend_name": friend_name,
                "status": status,
                "error": error,
            },
        )
    if inserted > 0:
        _emit(
            session,
            event_type="friend.feed_item_discovered",
            target_type="friend_feed_source",
            target_id=source_id,
            payload={
                "source_id": source_id,
                "friend_id": friend_id,
                "friend_name": friend_name,
                "inserted": inserted,
                "feed_url_updated": feed_url_updated,
            },
        )


def emit_friend_feed_source_created(
    session,
    *,
    source_id: str,
    friend_id: str,
    feed_url: str,
) -> None:
    _emit(
        session,
        event_type="friend.feed_source.created",
        target_type="friend_feed_source",
        target_id=source_id,
        payload={"source_id": source_id, "friend_id": friend_id, "feed_url": feed_url},
    )


def emit_friend_feed_source_updated(
    session,
    *,
    source_id: str,
    friend_id: str,
    feed_url: str,
    changed_fields: list[str],
) -> None:
    _emit(
        session,
        event_type="friend.feed_source.updated",
        target_type="friend_feed_source",
        target_id=source_id,
        payload={
            "source_id": source_id,
            "friend_id": friend_id,
            "feed_url": feed_url,
            "changed_fields": changed_fields,
        },
    )


def emit_friend_feed_source_deleted(
    session,
    *,
    source_id: str,
    friend_id: str,
    feed_url: str,
) -> None:
    _emit(
        session,
        event_type="friend.feed_source.deleted",
        target_type="friend_feed_source",
        target_id=source_id,
        payload={"source_id": source_id, "friend_id": friend_id, "feed_url": feed_url},
    )


def emit_asset_uploaded(
    session,
    *,
    asset_id: str,
    resource_key: str,
    visibility: str,
    scope: str,
    category: str,
    file_name: str,
) -> None:
    _emit(
        session,
        event_type="asset.uploaded",
        target_type="asset",
        target_id=asset_id,
        payload={
            "asset_id": asset_id,
            "resource_key": resource_key,
            "visibility": visibility,
            "scope": scope,
            "category": category,
            "file_name": file_name,
        },
    )


def emit_asset_updated(
    session,
    *,
    asset_id: str,
    resource_key: str,
    visibility: str,
    scope: str,
    category: str,
) -> None:
    _emit(
        session,
        event_type="asset.updated",
        target_type="asset",
        target_id=asset_id,
        payload={
            "asset_id": asset_id,
            "resource_key": resource_key,
            "visibility": visibility,
            "scope": scope,
            "category": category,
        },
    )


def emit_asset_deleted(session, *, asset_id: str, resource_key: str, file_name: str) -> None:
    _emit(
        session,
        event_type="asset.deleted",
        target_type="asset",
        target_id=asset_id,
        payload={"asset_id": asset_id, "resource_key": resource_key, "file_name": file_name},
    )


def emit_asset_bulk_deleted(session, *, ids: list[str], affected: int) -> None:
    _emit(
        session,
        event_type="asset.bulk_deleted",
        target_type="asset_batch",
        target_id=str(ids[0] if ids else "asset-batch"),
        payload={"asset_ids": ids, "affected": affected},
    )


def emit_comment_image_saved(
    session,
    *,
    asset_id: str,
    resource_key: str,
    file_name: str,
) -> None:
    _emit(
        session,
        event_type="asset.comment_image_saved",
        target_type="asset",
        target_id=asset_id,
        payload={"asset_id": asset_id, "resource_key": resource_key, "file_name": file_name, "category": "comment"},
    )


def emit_site_auth_config_updated(
    session,
    *,
    changed_fields: list[str],
    visitor_oauth_providers: list[str],
    admin_auth_methods: list[str],
    email_login_enabled: bool,
    admin_email_enabled: bool,
) -> None:
    _emit(
        session,
        event_type="site_auth.config_updated",
        target_type="site_auth_config",
        target_id="site-auth-config",
        payload={
            "changed_fields": changed_fields,
            "visitor_oauth_providers": visitor_oauth_providers,
            "admin_auth_methods": admin_auth_methods,
            "email_login_enabled": email_login_enabled,
            "admin_email_enabled": admin_email_enabled,
        },
    )


def emit_site_user_session_created(session, *, site_user_id: str) -> None:
    _emit(
        session,
        event_type="site_user.session_created",
        target_type="site_user",
        target_id=site_user_id,
        payload={"site_user_id": site_user_id},
    )


def emit_site_user_session_deleted(session, *, site_user_id: str) -> None:
    _emit(
        session,
        event_type="site_user.session_deleted",
        target_type="site_user",
        target_id=site_user_id,
        payload={"site_user_id": site_user_id},
    )


def emit_site_user_profile_updated(
    session,
    *,
    site_user_id: str,
    display_name: str,
    avatar_url: str,
) -> None:
    _emit(
        session,
        event_type="site_user.profile_updated",
        target_type="site_user",
        target_id=site_user_id,
        payload={
            "site_user_id": site_user_id,
            "display_name": display_name,
            "avatar_url": avatar_url,
        },
    )


def emit_site_admin_identity_created(
    session,
    *,
    identity_id: str,
    site_user_id: str,
    provider: str,
    email: str,
) -> None:
    _emit(
        session,
        event_type="site_admin_identity.created",
        target_type="site_admin_identity",
        target_id=identity_id,
        payload={
            "identity_id": identity_id,
            "site_user_id": site_user_id,
            "provider": provider,
            "email": email,
        },
    )


def emit_site_admin_identity_deleted(
    session,
    *,
    identity_id: str,
    site_user_id: str,
    provider: str,
    email: str,
) -> None:
    _emit(
        session,
        event_type="site_admin_identity.deleted",
        target_type="site_admin_identity",
        target_id=identity_id,
        payload={
            "identity_id": identity_id,
            "site_user_id": site_user_id,
            "provider": provider,
            "email": email,
        },
    )
