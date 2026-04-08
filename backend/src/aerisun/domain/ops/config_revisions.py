from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.domain.automation.schemas import AgentWorkflowRead
from aerisun.domain.automation.settings import (
    AGENT_MODEL_CONFIG_FLAG_KEY,
    AGENT_WORKFLOWS_FLAG_KEY,
    list_agent_workflows,
)
from aerisun.domain.automation.settings import (
    get_agent_model_config as get_agent_model_config_read,
)
from aerisun.domain.exceptions import ResourceNotFound, StateConflict
from aerisun.domain.media.object_storage import (
    get_object_storage_config_read,
    restore_object_storage_config,
)
from aerisun.domain.ops.models import AuditLog, ConfigRevision
from aerisun.domain.outbound_proxy.service import (
    get_outbound_proxy_config,
    restore_outbound_proxy_config,
)
from aerisun.domain.site_auth.config_service import get_site_auth_config_orm
from aerisun.domain.site_config import repository as site_repo
from aerisun.domain.site_config.models import (
    CommunityConfig,
    NavItem,
    PageCopy,
    Poem,
    SiteProfile,
    SocialLink,
)
from aerisun.domain.site_config.schemas import normalize_comment_moderation_mode
from aerisun.domain.subscription.service import get_subscription_config_orm

RESOURCE_VERSION = "2026-03-config-v1"
RestoreTarget = Literal["before", "after"]

_SENSITIVE_EXACT_FIELDS = {
    "smtp_password",
    "smtp_oauth_client_secret",
    "smtp_oauth_refresh_token",
    "google_client_secret",
    "github_client_secret",
    "api_key",
}
_SENSITIVE_KEYWORDS = ("secret", "password", "token", "api_key")


@dataclass(frozen=True, slots=True)
class ConfigResourceSpec:
    key: str
    label: str
    resource_version: str
    capture: Callable[[Session], Any]
    restore: Callable[[Session, Any], None]
    summarize: Callable[[str, list[str]], str] | None = None


def _ordered_json(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: _ordered_json(data[key]) for key in sorted(data)}
    if isinstance(data, list):
        return [_ordered_json(item) for item in data]
    return data


def canonicalize_snapshot(data: Any) -> Any:
    return json.loads(json.dumps(_ordered_json(data), ensure_ascii=False, default=str))


def _coerce_hero_actions(raw_value: str | None) -> list[dict[str, Any]]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _path_key(path: str) -> str:
    if not path:
        return ""
    normalized = path.replace("[", ".").replace("]", "")
    parts = [part for part in normalized.split(".") if part]
    return parts[-1].lower() if parts else path.lower()


def is_sensitive_path(path: str) -> bool:
    field_name = _path_key(path)
    if field_name in _SENSITIVE_EXACT_FIELDS:
        return True
    return any(keyword in field_name for keyword in _SENSITIVE_KEYWORDS)


def collect_sensitive_fields(data: Any, *, prefix: str = "") -> list[str]:
    fields: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if is_sensitive_path(path):
                fields.append(path)
            fields.extend(collect_sensitive_fields(value, prefix=path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            fields.extend(collect_sensitive_fields(value, prefix=path))
    return sorted(set(fields))


def _mask_sensitive_scalar(value: Any) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    if len(text) <= 4:
        return "******"
    return f"******{text[-4:]}"


def mask_snapshot(data: Any, *, prefix: str = "") -> Any:
    if isinstance(data, dict):
        masked: dict[str, Any] = {}
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if is_sensitive_path(path):
                masked[key] = _mask_sensitive_scalar(value)
            else:
                masked[key] = mask_snapshot(value, prefix=path)
        return masked
    if isinstance(data, list):
        return [
            mask_snapshot(item, prefix=f"{prefix}[{index}]" if prefix else f"[{index}]")
            for index, item in enumerate(data)
        ]
    return data


def _json_value_repr(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _flatten_json(data: Any, *, prefix: str = "") -> dict[str, Any]:
    if isinstance(data, dict):
        flattened: dict[str, Any] = {}
        if not data and prefix:
            flattened[prefix] = {}
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten_json(value, prefix=path))
        return flattened
    if isinstance(data, list):
        flattened = {}
        if not data and prefix:
            flattened[prefix] = []
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            flattened.update(_flatten_json(value, prefix=path))
        return flattened
    return {prefix or "$": data}


def diff_paths(before_preview: Any, after_preview: Any) -> list[str]:
    before_map = _flatten_json(before_preview)
    after_map = _flatten_json(after_preview)
    keys = sorted(set(before_map) | set(after_map))
    return [key for key in keys if before_map.get(key) != after_map.get(key)]


def build_diff_lines(before_preview: Any, after_preview: Any) -> list[dict[str, str]]:
    before_map = _flatten_json(before_preview)
    after_map = _flatten_json(after_preview)
    lines: list[dict[str, str]] = []
    for path in diff_paths(before_preview, after_preview):
        lines.append(
            {
                "path": path,
                "before": _json_value_repr(before_map.get(path)),
                "after": _json_value_repr(after_map.get(path)),
            }
        )
    return lines


def default_summary(resource_label: str, operation: str, changed_fields: list[str]) -> str:
    if operation == "restore":
        return f"{resource_label} 已恢复"
    if not changed_fields:
        return f"{resource_label} 已更新"
    return f"{resource_label} 已更新 {len(changed_fields)} 项配置"


def _config_action(resource_key: str, operation: str) -> str:
    return f"CONFIG {operation.upper()} {resource_key}"


def _config_audit_payload(revision: ConfigRevision) -> dict[str, Any]:
    return {
        "config_revision_id": revision.id,
        "resource_key": revision.resource_key,
        "summary": revision.summary,
    }


def create_config_audit_log(
    session: Session,
    *,
    actor_id: str | None,
    resource_key: str,
    revision: ConfigRevision,
) -> AuditLog:
    log = AuditLog(
        actor_type="admin",
        actor_id=actor_id,
        action=_config_action(resource_key, revision.operation),
        target_type=resource_key,
        target_id=revision.id,
        payload=_config_audit_payload(revision),
    )
    session.add(log)
    return log


def create_config_revision(
    session: Session,
    *,
    actor_id: str | None,
    resource_key: str,
    operation: str,
    before_snapshot: Any,
    after_snapshot: Any,
    restored_from_revision_id: str | None = None,
    summary_override: str | None = None,
    commit: bool = True,
) -> ConfigRevision:
    spec = get_config_resource_spec(resource_key)
    canonical_before = canonicalize_snapshot(before_snapshot)
    canonical_after = canonicalize_snapshot(after_snapshot)
    before_preview = canonicalize_snapshot(mask_snapshot(canonical_before))
    after_preview = canonicalize_snapshot(mask_snapshot(canonical_after))
    changed_fields = diff_paths(before_preview, after_preview)
    sensitive_fields = sorted(
        set(collect_sensitive_fields(canonical_before)) | set(collect_sensitive_fields(canonical_after))
    )
    summary_builder = spec.summarize or (lambda op, fields: default_summary(spec.label, op, fields))
    revision = ConfigRevision(
        actor_id=actor_id,
        resource_key=spec.key,
        resource_label=spec.label,
        operation=operation,
        resource_version=spec.resource_version,
        summary=summary_override or summary_builder(operation, changed_fields),
        changed_fields=changed_fields,
        before_snapshot=canonical_before,
        after_snapshot=canonical_after,
        before_preview=before_preview,
        after_preview=after_preview,
        sensitive_fields=sensitive_fields,
        restored_from_revision_id=restored_from_revision_id,
    )
    session.add(revision)
    session.flush()
    create_config_audit_log(session, actor_id=actor_id, resource_key=resource_key, revision=revision)
    if commit:
        session.commit()
        session.refresh(revision)
    return revision


def capture_config_resource(session: Session, resource_key: str) -> Any:
    return get_config_resource_spec(resource_key).capture(session)


def list_config_revisions(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    resource_key: str | None = None,
    actor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[ConfigRevision], int]:
    query = session.query(ConfigRevision)
    if resource_key:
        query = query.filter(ConfigRevision.resource_key == resource_key)
    if actor_id:
        query = query.filter(ConfigRevision.actor_id == actor_id)
    if date_from:
        query = query.filter(ConfigRevision.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(ConfigRevision.created_at <= datetime.fromisoformat(date_to))
    total = query.count()
    items = list(query.order_by(ConfigRevision.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all())
    return items, total


def get_config_revision(session: Session, revision_id: str) -> ConfigRevision:
    revision = session.get(ConfigRevision, revision_id)
    if revision is None:
        raise ResourceNotFound("Config revision not found")
    return revision


def restore_config_revision(
    session: Session,
    *,
    revision_id: str,
    actor_id: str | None,
    target: RestoreTarget = "before",
    reason: str | None = None,
) -> ConfigRevision:
    revision = get_config_revision(session, revision_id)
    spec = get_config_resource_spec(revision.resource_key)
    if revision.resource_version != spec.resource_version:
        raise StateConflict("Config revision version is not supported by the current restore handler")
    snapshot = revision.before_snapshot if target == "before" else revision.after_snapshot
    if snapshot is None:
        raise StateConflict("Selected revision snapshot is not restorable")
    current_before = capture_config_resource(session, spec.key)
    spec.restore(session, snapshot)
    current_after = capture_config_resource(session, spec.key)
    summary = f"{spec.label} 已恢复到 {target} 快照"
    if reason:
        summary = f"{summary}：{reason}"
    restored_revision = create_config_revision(
        session,
        actor_id=actor_id,
        resource_key=spec.key,
        operation="restore",
        before_snapshot=current_before,
        after_snapshot=current_after,
        restored_from_revision_id=revision.id,
        summary_override=summary,
        commit=False,
    )
    session.commit()
    session.refresh(restored_revision)
    return restored_revision


def is_tracked_config_request(path: str, method: str) -> bool:
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    if path.startswith("/api/v1/admin/system/config-revisions/"):
        return path.endswith("/restore")
    if path == "/api/v1/admin/site-config/profile":
        return method == "PUT"
    if path == "/api/v1/admin/site-config/community-config":
        return method == "PUT"
    if path.startswith("/api/v1/admin/site-config/social-links"):
        return True
    if path.startswith("/api/v1/admin/site-config/poems"):
        return True
    if path.startswith("/api/v1/admin/site-config/page-copy"):
        return True
    if path.startswith("/api/v1/admin/site-config/nav-items"):
        return True
    if path == "/api/v1/admin/visitors/config":
        return method == "PUT"
    if path == "/api/v1/admin/subscriptions/config":
        return method == "PUT"
    if path == "/api/v1/admin/proxy-config":
        return method == "PUT"
    if path == "/api/v1/admin/object-storage/config":
        return method == "PUT"
    if path == "/api/v1/admin/integrations/mcp-config":
        return method == "PUT"
    if path == "/api/v1/admin/automation/model-config":
        return method == "PUT"
    if path == "/api/v1/admin/automation/workflows":
        return method == "POST"
    if path.startswith("/api/v1/admin/automation/workflows/"):
        return method in {"PUT", "DELETE"}
    return False


def _site_profile_capture(session: Session) -> dict[str, Any]:
    profile = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    return canonicalize_snapshot(
        {
            "name": profile.name,
            "title": profile.title,
            "bio": profile.bio,
            "role": profile.role,
            "og_image": profile.og_image,
            "site_icon_url": profile.site_icon_url,
            "hero_image_url": profile.hero_image_url,
            "hero_poster_url": profile.hero_poster_url,
            "filing_info": profile.filing_info,
            "hero_actions": _coerce_hero_actions(profile.hero_actions),
            "hero_video_url": profile.hero_video_url,
            "poem_source": profile.poem_source,
            "poem_hitokoto_types": list(profile.poem_hitokoto_types or []),
            "poem_hitokoto_keywords": list(profile.poem_hitokoto_keywords or []),
            "feature_flags": dict(profile.feature_flags or {}),
        }
    )


def _site_profile_restore(session: Session, snapshot: dict[str, Any]) -> None:
    profile = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    for key, value in snapshot.items():
        if key == "hero_actions":
            profile.hero_actions = json.dumps(value, ensure_ascii=False)
        elif key == "feature_flags":
            profile.feature_flags = dict(value or {})
        else:
            setattr(profile, key, value)
    session.flush()


def _community_capture(session: Session) -> dict[str, Any]:
    config = session.scalars(select(CommunityConfig).order_by(CommunityConfig.created_at.asc())).first()
    if config is None:
        raise ResourceNotFound("Community config not configured")
    return canonicalize_snapshot(
        {
            "provider": config.provider,
            "server_url": config.server_url,
            "surfaces": list(config.surfaces or []),
            "meta": list(config.meta or []),
            "required_meta": list(config.required_meta or []),
            "emoji_presets": list(config.emoji_presets or []),
            "image_uploader": config.image_uploader,
            "anonymous_enabled": config.anonymous_enabled,
            "moderation_mode": normalize_comment_moderation_mode(config.moderation_mode),
            "default_sorting": config.default_sorting,
            "page_size": config.page_size,
            "image_max_bytes": config.image_max_bytes,
            "avatar_helper_copy": config.avatar_helper_copy,
            "migration_state": config.migration_state,
        }
    )


def _community_restore(session: Session, snapshot: dict[str, Any]) -> None:
    config = session.scalars(select(CommunityConfig).order_by(CommunityConfig.created_at.asc())).first()
    if config is None:
        raise ResourceNotFound("Community config not configured")
    for key, value in snapshot.items():
        if key == "moderation_mode":
            value = normalize_comment_moderation_mode(value)
        setattr(config, key, value)
    session.flush()


def _capture_social_links(session: Session) -> list[dict[str, Any]]:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    items = (
        session.query(SocialLink)
        .filter(SocialLink.site_profile_id == profile.id)
        .order_by(SocialLink.order_index.asc(), SocialLink.id.asc())
        .all()
    )
    return canonicalize_snapshot(
        [
            {
                "id": item.id,
                "site_profile_id": item.site_profile_id,
                "name": item.name,
                "href": item.href,
                "icon_key": item.icon_key,
                "placement": item.placement,
                "order_index": item.order_index,
            }
            for item in items
        ]
    )


def _restore_social_links(session: Session, snapshot: list[dict[str, Any]]) -> None:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    session.query(SocialLink).filter(SocialLink.site_profile_id == profile.id).delete(synchronize_session=False)
    session.flush()
    for item in snapshot:
        session.add(SocialLink(**item))
    session.flush()


def _capture_poems(session: Session) -> list[dict[str, Any]]:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    items = (
        session.query(Poem)
        .filter(Poem.site_profile_id == profile.id)
        .order_by(Poem.order_index.asc(), Poem.id.asc())
        .all()
    )
    return canonicalize_snapshot(
        [
            {
                "id": item.id,
                "site_profile_id": item.site_profile_id,
                "order_index": item.order_index,
                "content": item.content,
            }
            for item in items
        ]
    )


def _restore_poems(session: Session, snapshot: list[dict[str, Any]]) -> None:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    session.query(Poem).filter(Poem.site_profile_id == profile.id).delete(synchronize_session=False)
    session.flush()
    for item in snapshot:
        session.add(Poem(**item))
    session.flush()


def _capture_navigation(session: Session) -> list[dict[str, Any]]:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    items = (
        session.query(NavItem)
        .filter(NavItem.site_profile_id == profile.id)
        .order_by(NavItem.order_index.asc(), NavItem.id.asc())
        .all()
    )
    return canonicalize_snapshot(
        [
            {
                "id": item.id,
                "site_profile_id": item.site_profile_id,
                "parent_id": item.parent_id,
                "label": item.label,
                "href": item.href,
                "icon_key": item.icon_key,
                "page_key": item.page_key,
                "trigger": item.trigger,
                "order_index": item.order_index,
                "is_enabled": item.is_enabled,
            }
            for item in items
        ]
    )


def _restore_navigation(session: Session, snapshot: list[dict[str, Any]]) -> None:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    session.query(NavItem).filter(NavItem.site_profile_id == profile.id).delete(synchronize_session=False)
    session.flush()
    roots = [item for item in snapshot if not item.get("parent_id")]
    children = [item for item in snapshot if item.get("parent_id")]
    for item in [*roots, *children]:
        session.add(NavItem(**item))
    session.flush()


def _capture_pages(session: Session) -> dict[str, Any]:
    copies = session.query(PageCopy).order_by(PageCopy.page_key.asc()).all()
    return canonicalize_snapshot(
        {
            "page_copy": [
                {
                    "id": item.id,
                    "page_key": item.page_key,
                    "title": item.title,
                    "subtitle": item.subtitle,
                    "search_placeholder": item.search_placeholder,
                    "empty_message": item.empty_message,
                    "max_width": item.max_width,
                    "page_size": item.page_size,
                    "extras": dict(item.extras or {}),
                }
                for item in copies
            ],
        }
    )


def _restore_pages(session: Session, snapshot: dict[str, Any]) -> None:
    session.query(PageCopy).delete(synchronize_session=False)
    session.flush()
    allowed_page_copy_fields = {
        "id",
        "page_key",
        "title",
        "subtitle",
        "search_placeholder",
        "empty_message",
        "max_width",
        "page_size",
        "extras",
    }
    for item in snapshot.get("page_copy", []):
        session.add(PageCopy(**{key: value for key, value in item.items() if key in allowed_page_copy_fields}))
    session.flush()


def _capture_visitors_auth(session: Session) -> dict[str, Any]:
    config = get_site_auth_config_orm(session)
    return canonicalize_snapshot(
        {
            "email_login_enabled": config.email_login_enabled,
            "visitor_oauth_providers": list(config.visitor_oauth_providers or []),
            "admin_auth_methods": list(config.admin_auth_methods or []),
            "admin_console_auth_methods": list(config.admin_console_auth_methods or []),
            "admin_email_enabled": config.admin_email_enabled,
            "admin_email_password_hash": config.admin_email_password_hash,
            "google_client_id": config.google_client_id,
            "google_client_secret": config.google_client_secret,
            "github_client_id": config.github_client_id,
            "github_client_secret": config.github_client_secret,
        }
    )


def _restore_visitors_auth(session: Session, snapshot: dict[str, Any]) -> None:
    config = get_site_auth_config_orm(session)
    for key, value in snapshot.items():
        setattr(config, key, value)
    session.flush()


def _capture_subscriptions_config(session: Session) -> dict[str, Any]:
    config = get_subscription_config_orm(session)
    return canonicalize_snapshot(
        {
            "enabled": config.enabled,
            "smtp_auth_mode": config.smtp_auth_mode,
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "smtp_username": config.smtp_username,
            "smtp_password": config.smtp_password,
            "smtp_oauth_tenant": config.smtp_oauth_tenant,
            "smtp_oauth_client_id": config.smtp_oauth_client_id,
            "smtp_oauth_client_secret": config.smtp_oauth_client_secret,
            "smtp_oauth_refresh_token": config.smtp_oauth_refresh_token,
            "smtp_from_email": config.smtp_from_email,
            "smtp_from_name": config.smtp_from_name,
            "smtp_reply_to": config.smtp_reply_to,
            "smtp_use_tls": config.smtp_use_tls,
            "smtp_use_ssl": config.smtp_use_ssl,
            "smtp_test_passed": config.smtp_test_passed,
            "smtp_tested_at": config.smtp_tested_at.isoformat() if config.smtp_tested_at else None,
            "allowed_content_types": list(config.allowed_content_types or []),
            "mail_subject_template": config.mail_subject_template,
            "mail_body_template": config.mail_body_template,
        }
    )


def _restore_subscriptions_config(session: Session, snapshot: dict[str, Any]) -> None:
    config = get_subscription_config_orm(session)
    for key, value in snapshot.items():
        if key == "smtp_tested_at":
            setattr(config, key, datetime.fromisoformat(value) if value else None)
        else:
            setattr(config, key, value)
    session.flush()


def _capture_mcp_public_access(session: Session) -> dict[str, bool]:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    return canonicalize_snapshot({"public_access": bool((profile.feature_flags or {}).get("mcp_public_access", False))})


def _restore_mcp_public_access(session: Session, snapshot: dict[str, bool]) -> None:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    feature_flags = dict(profile.feature_flags or {})
    feature_flags["mcp_public_access"] = bool(snapshot.get("public_access", False))
    profile.feature_flags = feature_flags
    session.flush()


def _capture_outbound_proxy_config(session: Session) -> dict[str, Any]:
    return canonicalize_snapshot(get_outbound_proxy_config(session).model_dump())


def _restore_outbound_proxy_config(session: Session, snapshot: dict[str, Any]) -> None:
    restore_outbound_proxy_config(session, snapshot)


def _capture_object_storage_config(session: Session) -> dict[str, Any]:
    payload = get_object_storage_config_read(session).model_dump()
    payload["secret_key"] = None
    payload["cdn_token_key"] = None
    return canonicalize_snapshot(payload)


def _restore_object_storage_config_snapshot(session: Session, snapshot: dict[str, Any]) -> None:
    restore_object_storage_config(session, snapshot)


def _capture_agent_model_config(session: Session) -> dict[str, Any]:
    config = get_agent_model_config_read(session)
    return canonicalize_snapshot(config.model_dump(exclude={"is_ready"}))


def _restore_agent_model_config(session: Session, snapshot: dict[str, Any]) -> None:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    feature_flags = dict(profile.feature_flags or {})
    feature_flags[AGENT_MODEL_CONFIG_FLAG_KEY] = dict(snapshot or {})
    profile.feature_flags = feature_flags
    session.flush()


def _capture_agent_workflows(session: Session) -> list[dict[str, Any]]:
    return canonicalize_snapshot(
        [workflow.model_dump(exclude={"built_in"}) for workflow in list_agent_workflows(session)]
    )


def _restore_agent_workflows(session: Session, snapshot: list[dict[str, Any]]) -> None:
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    normalized = [AgentWorkflowRead.model_validate(item).model_dump(exclude={"built_in"}) for item in snapshot]
    feature_flags = dict(profile.feature_flags or {})
    feature_flags[AGENT_WORKFLOWS_FLAG_KEY] = normalized
    profile.feature_flags = feature_flags
    session.flush()


def _static_summary(label: str) -> Callable[[str, list[str]], str]:
    return lambda operation, fields: default_summary(label, operation, fields)


_CONFIG_RESOURCES: dict[str, ConfigResourceSpec] = {
    "site.profile": ConfigResourceSpec(
        key="site.profile",
        label="站点资料",
        resource_version=RESOURCE_VERSION,
        capture=_site_profile_capture,
        restore=_site_profile_restore,
        summarize=_static_summary("站点资料"),
    ),
    "site.community": ConfigResourceSpec(
        key="site.community",
        label="社区配置",
        resource_version=RESOURCE_VERSION,
        capture=_community_capture,
        restore=_community_restore,
        summarize=_static_summary("社区配置"),
    ),
    "site.navigation": ConfigResourceSpec(
        key="site.navigation",
        label="导航配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_navigation,
        restore=_restore_navigation,
        summarize=_static_summary("导航配置"),
    ),
    "site.social_links": ConfigResourceSpec(
        key="site.social_links",
        label="社交链接",
        resource_version=RESOURCE_VERSION,
        capture=_capture_social_links,
        restore=_restore_social_links,
        summarize=_static_summary("社交链接"),
    ),
    "site.poems": ConfigResourceSpec(
        key="site.poems",
        label="诗句配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_poems,
        restore=_restore_poems,
        summarize=_static_summary("诗句配置"),
    ),
    "site.pages": ConfigResourceSpec(
        key="site.pages",
        label="页面配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_pages,
        restore=_restore_pages,
        summarize=_static_summary("页面配置"),
    ),
    "visitors.auth": ConfigResourceSpec(
        key="visitors.auth",
        label="访客认证配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_visitors_auth,
        restore=_restore_visitors_auth,
        summarize=_static_summary("访客认证配置"),
    ),
    "subscriptions.config": ConfigResourceSpec(
        key="subscriptions.config",
        label="订阅配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_subscriptions_config,
        restore=_restore_subscriptions_config,
        summarize=_static_summary("订阅配置"),
    ),
    "network.outbound_proxy": ConfigResourceSpec(
        key="network.outbound_proxy",
        label="出站代理",
        resource_version=RESOURCE_VERSION,
        capture=_capture_outbound_proxy_config,
        restore=_restore_outbound_proxy_config,
        summarize=_static_summary("出站代理"),
    ),
    "integrations.object_storage": ConfigResourceSpec(
        key="integrations.object_storage",
        label="对象存储",
        resource_version=RESOURCE_VERSION,
        capture=_capture_object_storage_config,
        restore=_restore_object_storage_config_snapshot,
        summarize=_static_summary("对象存储"),
    ),
    "integrations.mcp_public_access": ConfigResourceSpec(
        key="integrations.mcp_public_access",
        label="MCP 公共访问配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_mcp_public_access,
        restore=_restore_mcp_public_access,
        summarize=_static_summary("MCP 公共访问配置"),
    ),
    "automation.model_config": ConfigResourceSpec(
        key="automation.model_config",
        label="Agent 模型配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_agent_model_config,
        restore=_restore_agent_model_config,
        summarize=_static_summary("Agent 模型配置"),
    ),
    "automation.workflows": ConfigResourceSpec(
        key="automation.workflows",
        label="Agent 工作流配置",
        resource_version=RESOURCE_VERSION,
        capture=_capture_agent_workflows,
        restore=_restore_agent_workflows,
        summarize=_static_summary("Agent 工作流配置"),
    ),
}


def get_config_resource_spec(resource_key: str) -> ConfigResourceSpec:
    try:
        return _CONFIG_RESOURCES[resource_key]
    except KeyError as exc:
        raise ResourceNotFound("Config resource not found") from exc
