from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.agent.schemas import McpAdminConfigRead, McpAdminConfigUpdate
from aerisun.domain.agent.service import build_agent_usage, build_mcp_admin_config, save_mcp_admin_config
from aerisun.domain.content.feed_service import list_feed_definitions
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.iam.schemas import ApiKeyAdminRead, ApiKeyCreate, ApiKeyCreateResponse, ApiKeyUpdate
from aerisun.domain.iam.service import (
    create_api_key as _create_api_key,
)
from aerisun.domain.iam.service import (
    delete_api_key as _delete_api_key,
)
from aerisun.domain.iam.service import (
    list_api_keys as _list_api_keys,
)
from aerisun.domain.iam.service import (
    update_api_key as _update_api_key,
)
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
from aerisun.domain.ops.schemas import (
    AuditLogRead,
    BackupSnapshotRead,
    ConfigRevisionDetailRead,
    ConfigRevisionListItemRead,
    ConfigRevisionRestoreWrite,
    EnhancedDashboardStats,
    SystemInfo,
    VisitorRecordRead,
)
from aerisun.domain.ops.service import create_backup_snapshot as _create_backup
from aerisun.domain.ops.service import get_config_revision_detail as _get_config_revision_detail
from aerisun.domain.ops.service import get_dashboard_stats as _get_dashboard_stats
from aerisun.domain.ops.service import get_system_info as _get_system_info
from aerisun.domain.ops.service import list_audit_logs as _list_audit_logs
from aerisun.domain.ops.service import list_backups as _list_backups
from aerisun.domain.ops.service import list_config_revisions as _list_config_revisions
from aerisun.domain.ops.service import list_visitor_records as _list_visitor_records
from aerisun.domain.ops.service import restore_backup as _restore_backup
from aerisun.domain.ops.service import restore_config_revision as _restore_config_revision

from .deps import get_current_admin
from .integrations_schemas import AdminAgentUsageRead, FeedLinkCollectionRead, FeedLinkRead
from .schemas import PaginatedResponse

router = APIRouter(prefix="/system", tags=["admin-system"])
integrations_router = APIRouter(prefix="/integrations", tags=["admin-integrations"])


@integrations_router.get("/api-keys", response_model=list[ApiKeyAdminRead], summary="获取 API 密钥列表")
def list_api_keys(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _list_api_keys(session)


@integrations_router.post(
    "/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED, summary="创建 API 密钥"
)
def create_api_key(
    payload: ApiKeyCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _create_api_key(session, payload.key_name, payload.scopes)


@integrations_router.put("/api-keys/{key_id}", response_model=ApiKeyAdminRead, summary="更新 API 密钥")
def update_api_key(
    key_id: str,
    payload: ApiKeyUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _update_api_key(session, key_id, payload)


@integrations_router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除 API 密钥")
def delete_api_key(
    key_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    _delete_api_key(session, key_id)


@integrations_router.get("/feeds", response_model=FeedLinkCollectionRead, summary="获取 Feed 列表")
def list_feeds(
    _admin: AdminUser = Depends(get_current_admin),
) -> FeedLinkCollectionRead:
    site_url = (get_settings().site_url or "https://example.com").rstrip("/")
    return FeedLinkCollectionRead(
        items=[
            FeedLinkRead(
                key=definition.key,
                title=definition.title,
                url=f"{site_url}{definition.feed_path}",
            )
            for definition in list_feed_definitions()
        ]
    )


@integrations_router.get("/agent-usage", response_model=AdminAgentUsageRead, summary="获取 Agent 使用说明")
def get_agent_usage(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AdminAgentUsageRead:
    settings = get_settings()
    usage = build_agent_usage(session, settings.site_url, None)
    return AdminAgentUsageRead(item=usage)


@integrations_router.get("/mcp-config", response_model=McpAdminConfigRead, summary="获取 MCP 配置")
def get_mcp_config(
    api_key_id: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> McpAdminConfigRead:
    settings = get_settings()
    return build_mcp_admin_config(session, settings.site_url, api_key_id)


@integrations_router.put("/mcp-config", response_model=McpAdminConfigRead, summary="更新 MCP 配置")
def update_mcp_config(
    payload: McpAdminConfigUpdate,
    api_key_id: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> McpAdminConfigRead:
    before_snapshot = capture_config_resource(session, "integrations.mcp_public_access")
    settings = get_settings()
    result = save_mcp_admin_config(session, settings.site_url, payload, api_key_id)
    after_snapshot = capture_config_resource(session, "integrations.mcp_public_access")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="integrations.mcp_public_access",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


@router.get("/api-keys", response_model=list[ApiKeyAdminRead], include_in_schema=False)
def list_api_keys_legacy(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _list_api_keys(session)


@router.post(
    "/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_api_key_legacy(
    payload: ApiKeyCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _create_api_key(session, payload.key_name, payload.scopes)


@router.put("/api-keys/{key_id}", include_in_schema=False)
def update_api_key_legacy(
    key_id: str,
    payload: ApiKeyUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _update_api_key(session, key_id, payload)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def delete_api_key_legacy(
    key_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    _delete_api_key(session, key_id)


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogRead], summary="获取审计日志")
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return _list_audit_logs(
        session,
        page=page,
        page_size=page_size,
        action=action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/config-revisions",
    response_model=PaginatedResponse[ConfigRevisionListItemRead],
    summary="获取配置变更历史",
)
def list_config_revisions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    resource_key: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return _list_config_revisions(
        session,
        page=page,
        page_size=page_size,
        resource_key=resource_key,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/config-revisions/{revision_id}", response_model=ConfigRevisionDetailRead, summary="获取配置历史详情")
def get_config_revision_detail(
    revision_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ConfigRevisionDetailRead:
    return _get_config_revision_detail(session, revision_id)


@router.post(
    "/config-revisions/{revision_id}/restore",
    response_model=ConfigRevisionDetailRead,
    summary="恢复配置历史版本",
)
def restore_config_revision(
    revision_id: str,
    payload: ConfigRevisionRestoreWrite,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ConfigRevisionDetailRead:
    return _restore_config_revision(session, revision_id=revision_id, actor_id=admin.id, payload=payload)


@router.get("/backups", response_model=list[BackupSnapshotRead], summary="获取备份列表")
def list_backups(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _list_backups(session)


@router.post("/backups", response_model=BackupSnapshotRead, status_code=status.HTTP_201_CREATED, summary="创建备份快照")
def trigger_backup(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _create_backup(session)


@router.post("/backups/{snapshot_id}/restore", response_model=BackupSnapshotRead, summary="从备份恢复")
def restore_backup(
    snapshot_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _restore_backup(session, snapshot_id)


@router.get("/dashboard/stats", response_model=EnhancedDashboardStats, summary="获取仪表盘统计")
def dashboard_stats(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _get_dashboard_stats(session)


@router.get("/visitor-records", response_model=PaginatedResponse[VisitorRecordRead], summary="获取访客访问记录")
def visitor_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    path: str | None = Query(default=None),
    ip: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    include_bots: bool = Query(default=False),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return _list_visitor_records(
        session,
        page=page,
        page_size=page_size,
        path=path,
        ip=ip,
        date_from=date_from,
        date_to=date_to,
        include_bots=include_bots,
    )


@router.get("/info", response_model=SystemInfo, summary="获取系统信息")
def system_info(
    _admin: AdminUser = Depends(get_current_admin),
) -> Any:
    return _get_system_info()
