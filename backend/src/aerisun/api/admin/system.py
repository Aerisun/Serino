from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
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
from aerisun.domain.ops.schemas import (
    AuditLogRead,
    BackupSnapshotRead,
    EnhancedDashboardStats,
    SystemInfo,
    VisitorRecordRead,
)
from aerisun.domain.ops.service import (
    create_backup_snapshot as _create_backup,
)
from aerisun.domain.ops.service import (
    get_dashboard_stats as _get_dashboard_stats,
)
from aerisun.domain.ops.service import (
    get_system_info as _get_system_info,
)
from aerisun.domain.ops.service import (
    list_audit_logs as _list_audit_logs,
)
from aerisun.domain.ops.service import (
    list_backups as _list_backups,
)
from aerisun.domain.ops.service import (
    list_visitor_records as _list_visitor_records,
)
from aerisun.domain.ops.service import (
    restore_backup as _restore_backup,
)

from .deps import get_current_admin
from .integrations_schemas import FeedLinkCollectionRead, FeedLinkRead
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
            FeedLinkRead(key="posts", title="Posts RSS", url=f"{site_url}/feeds/posts.xml"),
            FeedLinkRead(key="rss", title="RSS Alias", url=f"{site_url}/rss.xml"),
        ]
    )


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
