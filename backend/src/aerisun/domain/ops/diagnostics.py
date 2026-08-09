from __future__ import annotations

import logging
import re
import shutil
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from sqlalchemy import func, or_, select, text, update

from aerisun.api.admin.scopes import AGENT_CONNECT
from aerisun.core.base import utcnow
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.core.time import normalize_shanghai_datetime
from aerisun.domain.agent.mcp_introspection import list_registered_mcp_capabilities
from aerisun.domain.agent.mcp_settings import filter_capabilities_for_scopes
from aerisun.domain.automation.runtime import (
    probe_chatgpt_config,
    probe_model_config,
    record_model_source_probe,
)
from aerisun.domain.automation.settings import get_agent_model_config_resolved
from aerisun.domain.iam.models import ApiKey
from aerisun.domain.media.models import (
    Asset,
    AssetLocalDeleteQueueItem,
    AssetMirrorQueueItem,
    AssetRemoteDeleteQueueItem,
    AssetRemoteUploadQueueItem,
    ObjectStorageConfig,
)
from aerisun.domain.media.object_storage import BitifulObjectStorageProvider
from aerisun.domain.ops.backup_sync import (
    get_backup_sync_config,
    probe_backup_machine_connection,
    probe_backup_write_access,
)
from aerisun.domain.ops.diagnostic_repository import (
    DIAGNOSTIC_RUN_ABANDONED_AFTER,
    claim_diagnostic_run,
    complete_diagnostic_run,
    get_diagnostic_state,
    try_queue_diagnostic_run,
)
from aerisun.domain.ops.diagnostic_schemas import (
    DiagnosticActionTarget,
    DiagnosticOverallStatus,
    DiagnosticTriggerKind,
    SystemDiagnosticItemRead,
    SystemDiagnosticStateRead,
)
from aerisun.domain.ops.models import BackupQueueItem, BackupTargetConfig
from aerisun.domain.ops.schemas import BackupSyncConfigUpdate
from aerisun.domain.outbound_proxy.service import (
    get_outbound_proxy_config,
)
from aerisun.domain.outbound_proxy.service import (
    test_outbound_proxy_config as run_outbound_proxy_test,
)
from aerisun.domain.site_config.service import mcp_public_access_enabled
from aerisun.domain.subscription.models import ContentSubscriptionConfig
from aerisun.domain.subscription.schemas import ContentSubscriptionConfigAdminRead
from aerisun.domain.subscription.service import (
    SMTP_SETTING_KEYS,
    get_subscription_config_orm,
    send_subscription_smtp_diagnostic_email,
)

logger = logging.getLogger("aerisun.diagnostics")

MODEL_DIAGNOSTIC_TIMEOUT_SECONDS = 15
BACKUP_MINIMUM_FRESHNESS_MINUTES = 120
DIAGNOSTIC_RESULT_STALE_AFTER = timedelta(hours=36)
_DETAIL_LIMIT = 400
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)(api[_-]?key|password|secret|refresh[_-]?token|access[_-]?token|authorization)"
    r"\s*[:=]\s*[^\s,;]+"
)


@dataclass(frozen=True, slots=True)
class DiagnosticCheckDefinition:
    key: str
    action_target: DiagnosticActionTarget
    checker: Callable[[], SystemDiagnosticItemRead]


@dataclass(frozen=True, slots=True)
class DiagnosticSummary:
    items: list[SystemDiagnosticItemRead]
    overall_status: DiagnosticOverallStatus
    healthy_count: int
    warning_count: int
    failed_count: int
    skipped_count: int
    issue_count: int


@dataclass(frozen=True, slots=True)
class QueueTaskHealth:
    failed_count: int
    retrying_count: int
    latest_completed_at: datetime | None


def _elapsed_ms(started_at: float) -> int:
    return max(int((time.perf_counter() - started_at) * 1000), 0)


def _item(
    *,
    key: str,
    status: Literal["healthy", "warning", "failed", "skipped"],
    summary: str,
    summary_key: str,
    action_target: DiagnosticActionTarget,
    summary_params: dict[str, str | int] | None = None,
    detail: str | None = None,
    detail_key: str | None = None,
    detail_params: dict[str, str | int] | None = None,
    started_at: float,
) -> SystemDiagnosticItemRead:
    return SystemDiagnosticItemRead(
        key=key,
        status=status,
        summary=summary,
        summary_key=summary_key,
        summary_params=summary_params or {},
        detail=detail,
        detail_key=detail_key,
        detail_params=detail_params or {},
        action_target=action_target,
        duration_ms=_elapsed_ms(started_at),
        checked_at=utcnow(),
    )


def _safe_detail(value: object, *, secrets: Sequence[str] = ()) -> str:
    detail = str(value or "").strip()
    for secret in sorted({item for item in secrets if len(item) >= 3}, key=len, reverse=True):
        detail = detail.replace(secret, "[已隐藏]")
    detail = _SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[已隐藏]", detail)
    return detail[:_DETAIL_LIMIT]


def aggregate_diagnostic_items(items: Sequence[SystemDiagnosticItemRead]) -> DiagnosticSummary:
    materialized = list(items)
    healthy_count = sum(item.status == "healthy" for item in materialized)
    warning_count = sum(item.status == "warning" for item in materialized)
    failed_count = sum(item.status == "failed" for item in materialized)
    skipped_count = sum(item.status == "skipped" for item in materialized)
    issue_count = warning_count + failed_count
    overall_status: DiagnosticOverallStatus = "attention" if issue_count else "healthy"
    return DiagnosticSummary(
        items=materialized,
        overall_status=overall_status,
        healthy_count=healthy_count,
        warning_count=warning_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        issue_count=issue_count,
    )


def check_database() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    with get_session_factory()() as session:
        session.execute(text("SELECT 1")).scalar_one()
    return _item(
        key="database",
        status="healthy",
        summary="数据库连接正常",
        summary_key="diagnostics.result.databaseHealthy",
        action_target="system",
        started_at=started_at,
    )


def _format_bytes(value: int) -> str:
    amount = float(max(value, 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"


def check_storage() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    settings = get_settings()
    paths = (
        Path(settings.data_dir),
        Path(settings.media_dir),
        Path(settings.secrets_dir),
        Path(settings.backup_sync_tmp_dir),
    )
    device_paths: dict[int, Path] = {}
    for path in paths:
        if not path.is_dir():
            return _item(
                key="storage",
                status="failed",
                summary="持久化目录不可用",
                summary_key="diagnostics.result.storageDirectoryUnavailable",
                detail=f"目录不存在或不是文件夹：{path}",
                detail_key="diagnostics.result.storageDirectoryMissingDetail",
                detail_params={"path": str(path)},
                action_target="system",
                started_at=started_at,
            )
        try:
            device = path.stat().st_dev
            device_paths.setdefault(device, path)
            with tempfile.NamedTemporaryFile(
                dir=path,
                prefix=".serino-diagnostic-",
                delete=True,
            ) as handle:
                handle.write(b"ok")
                handle.flush()
        except OSError as exc:
            return _item(
                key="storage",
                status="failed",
                summary="持久化目录不可写",
                summary_key="diagnostics.result.storageDirectoryUnwritable",
                detail=f"{path}：{_safe_detail(exc)}",
                action_target="system",
                started_at=started_at,
            )

    usage_details: list[str] = []
    low_space_paths: list[Path] = []
    for path in device_paths.values():
        try:
            usage = shutil.disk_usage(path)
        except OSError as exc:
            return _item(
                key="storage",
                status="failed",
                summary="无法读取持久化存储空间",
                summary_key="diagnostics.result.storageUsageUnavailable",
                detail=f"{path}：{_safe_detail(exc)}",
                action_target="system",
                started_at=started_at,
            )
        free_ratio = usage.free / usage.total if usage.total else 0.0
        usage_details.append(f"{path}: {_format_bytes(usage.free)} / {_format_bytes(usage.total)}")
        if free_ratio < 0.10 and usage.free < 5 * 1024**3:
            low_space_paths.append(path)

    detail = "；".join(usage_details)
    if low_space_paths:
        return _item(
            key="storage",
            status="warning",
            summary="持久化存储空间偏低",
            summary_key="diagnostics.result.storageLow",
            detail=detail,
            detail_key="diagnostics.result.storageUsageDetail",
            detail_params={"usage": detail},
            action_target="system",
            started_at=started_at,
        )
    return _item(
        key="storage",
        status="healthy",
        summary="持久化目录可写，磁盘空间正常",
        summary_key="diagnostics.result.storageHealthy",
        detail=detail,
        detail_key="diagnostics.result.storageUsageDetail",
        detail_params={"usage": detail},
        action_target="system",
        started_at=started_at,
    )


def check_model_api() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    with get_session_factory()() as session:
        config = get_agent_model_config_resolved(session)

    source_labels = {
        "chatgpt_oauth": "ChatGPT OAuth",
        "openai_compatible": "OpenAI-compatible API",
    }
    primary = config.primary_source
    order = [primary, *(source for source in source_labels if source != primary)]
    results: list[tuple[str, str, str]] = []
    any_incomplete = False
    for source in order:
        source_config = config.chatgpt_oauth if source == "chatgpt_oauth" else config.openai_compatible
        label = source_labels[source]
        if not source_config.enabled:
            results.append((source, "skipped", f"{label} 未启用"))
            continue
        if not source_config.is_ready:
            any_incomplete = True
            results.append((source, "failed", f"{label} 配置不完整"))
            continue

        payload = source_config.model_dump(exclude={"is_ready"})
        payload["timeout_seconds"] = min(int(source_config.timeout_seconds), MODEL_DIAGNOSTIC_TIMEOUT_SECONDS)
        try:
            probe = probe_chatgpt_config(payload) if source == "chatgpt_oauth" else probe_model_config(payload)
        except Exception as exc:
            record_model_source_probe(source, payload, error=exc)
            secrets = (
                (config.openai_compatible.api_key, config.openai_compatible.base_url)
                if source == "openai_compatible"
                else ()
            )
            results.append(
                (
                    source,
                    "failed",
                    f"{label}：{_safe_detail(exc, secrets=secrets)}",
                )
            )
            continue
        record_model_source_probe(source, payload)
        results.append((source, "healthy", f"{label}：模型 {probe.get('model') or source_config.model} 正常"))

    healthy_count = sum(status == "healthy" for _, status, _ in results)
    failed_count = sum(status == "failed" for _, status, _ in results)
    enabled_count = sum(status != "skipped" for _, status, _ in results)
    detail = "；".join(message for _, status, message in results if status != "skipped") or None

    if failed_count and healthy_count:
        return _item(
            key="model_api",
            status="warning",
            summary="一个模型来源不可用，自动容灾仍可工作",
            summary_key="diagnostics.result.modelDegraded",
            detail=detail,
            action_target="model_api",
            started_at=started_at,
        )
    if failed_count:
        return _item(
            key="model_api",
            status="failed",
            summary="当前没有可用的模型来源",
            summary_key=(
                "diagnostics.result.modelIncomplete" if any_incomplete else "diagnostics.result.modelProbeFailed"
            ),
            detail=detail,
            action_target="model_api",
            started_at=started_at,
        )
    if enabled_count == 0:
        return _item(
            key="model_api",
            status="skipped",
            summary="模型来源未启用",
            summary_key="diagnostics.result.modelDisabled",
            action_target="model_api",
            started_at=started_at,
        )
    return _item(
        key="model_api",
        status="healthy",
        summary="已启用的模型来源均响应正常",
        summary_key="diagnostics.result.modelHealthy",
        detail=detail,
        action_target="model_api",
        started_at=started_at,
    )


def check_smtp() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    with get_session_factory()() as session:
        config = get_subscription_config_orm(session)
        active = bool(config.enabled or config.comment_feedback_enabled)
        if not active:
            return _item(
                key="smtp",
                status="skipped",
                summary="邮件能力未启用",
                summary_key="diagnostics.result.smtpDisabled",
                action_target="smtp",
                started_at=started_at,
            )
        probe_config = ContentSubscriptionConfigAdminRead.model_validate(config)

    secrets = (
        probe_config.smtp_password,
        probe_config.smtp_oauth_client_secret,
        probe_config.smtp_oauth_refresh_token,
    )
    probe_error: Exception | None = None
    try:
        send_subscription_smtp_diagnostic_email(
            probe_config,
            timeout_seconds=10,
        )
    except Exception as exc:
        probe_error = exc

    match_fields = (
        *SMTP_SETTING_KEYS,
        "enabled",
        "comment_feedback_enabled",
        "smtp_test_passed",
    )
    with get_session_factory()() as session:
        conditions = [ContentSubscriptionConfig.id == probe_config.id]
        conditions.extend(
            getattr(ContentSubscriptionConfig, field) == getattr(probe_config, field)
            for field in match_fields
            if field != "smtp_oauth_refresh_token"
        )
        conditions.append(ContentSubscriptionConfig.smtp_oauth_refresh_token == secrets[2])
        result = session.execute(
            update(ContentSubscriptionConfig)
            .where(*conditions)
            .values(smtp_oauth_refresh_token=probe_config.smtp_oauth_refresh_token)
            .execution_options(synchronize_session=False)
        )
        snapshot_is_current = result.rowcount == 1
        session.commit()

    if not snapshot_is_current:
        return _item(
            key="smtp",
            status="warning",
            summary="邮箱配置在检查期间已更新",
            summary_key="diagnostics.result.smtpChanged",
            detail="旧配置的检查结果已丢弃，请重新运行一次诊断。",
            detail_key="diagnostics.result.smtpChangedDetail",
            action_target="smtp",
            started_at=started_at,
        )
    if probe_error is not None:
        return _item(
            key="smtp",
            status="failed",
            summary="SMTP 测试邮件发送失败",
            summary_key="diagnostics.result.smtpFailed",
            detail=_safe_detail(
                probe_error,
                secrets=(*secrets, probe_config.smtp_oauth_refresh_token),
            ),
            action_target="smtp",
            started_at=started_at,
        )
    return _item(
        key="smtp",
        status="healthy",
        summary="SMTP 测试邮件成功发送",
        summary_key="diagnostics.result.smtpHealthy",
        action_target="smtp",
        started_at=started_at,
    )


def _latest_queue_task_health(session, model, key_column) -> QueueTaskHealth:
    ranked = select(
        model.status.label("status"),
        model.retry_count.label("retry_count"),
        model.updated_at.label("updated_at"),
        func.row_number()
        .over(
            partition_by=key_column,
            order_by=(model.updated_at.desc(), model.created_at.desc(), model.id.desc()),
        )
        .label("position"),
    ).subquery()
    row = session.execute(
        select(
            func.count().filter(ranked.c.position == 1, ranked.c.status == "failed").label("failed_count"),
            func.count()
            .filter(
                ranked.c.position == 1,
                ranked.c.status.in_(("queued", "running", "retrying")),
                ranked.c.retry_count > 0,
            )
            .label("retrying_count"),
            func.max(ranked.c.updated_at)
            .filter(ranked.c.position == 1, ranked.c.status == "completed")
            .label("latest_completed_at"),
        ).select_from(ranked)
    ).one()
    return QueueTaskHealth(
        failed_count=int(row.failed_count or 0),
        retrying_count=int(row.retrying_count or 0),
        latest_completed_at=(
            normalize_shanghai_datetime(row.latest_completed_at) if row.latest_completed_at is not None else None
        ),
    )


def _object_storage_task_health(session) -> QueueTaskHealth:
    failed_asset_count = int(
        session.scalar(
            select(func.count())
            .select_from(Asset)
            .where(
                or_(
                    Asset.mirror_status == "failed",
                    Asset.remote_status.in_(("failed", "invalid")),
                )
            )
        )
        or 0
    )
    mirror = _latest_queue_task_health(session, AssetMirrorQueueItem, AssetMirrorQueueItem.asset_id)
    remote_upload = _latest_queue_task_health(
        session,
        AssetRemoteUploadQueueItem,
        AssetRemoteUploadQueueItem.asset_id,
    )
    remote_delete = _latest_queue_task_health(
        session,
        AssetRemoteDeleteQueueItem,
        AssetRemoteDeleteQueueItem.object_key,
    )
    local_delete = _latest_queue_task_health(
        session,
        AssetLocalDeleteQueueItem,
        AssetLocalDeleteQueueItem.storage_path,
    )
    completed_times = [
        value
        for value in (
            mirror.latest_completed_at,
            remote_upload.latest_completed_at,
            remote_delete.latest_completed_at,
            local_delete.latest_completed_at,
        )
        if value is not None
    ]
    return QueueTaskHealth(
        failed_count=failed_asset_count + remote_delete.failed_count + local_delete.failed_count,
        retrying_count=sum(item.retrying_count for item in (mirror, remote_upload, remote_delete, local_delete)),
        latest_completed_at=max(completed_times) if completed_times else None,
    )


def check_object_storage() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    with get_session_factory()() as session:
        config = session.scalars(select(ObjectStorageConfig).limit(1)).first()
        if config is None or not config.enabled:
            return _item(
                key="object_storage",
                status="skipped",
                summary="对象存储未启用",
                summary_key="diagnostics.result.objectStorageDisabled",
                action_target="object_storage",
                started_at=started_at,
            )
        secrets = (config.access_key, config.secret_key, config.cdn_token_key)
        required = (config.endpoint, config.bucket, config.access_key, config.secret_key)
        if not all(str(value or "").strip() for value in required):
            return _item(
                key="object_storage",
                status="failed",
                summary="对象存储配置不完整",
                summary_key="diagnostics.result.objectStorageIncomplete",
                detail="请检查 Endpoint、Bucket、Access Key 和 Secret Key。",
                detail_key="diagnostics.result.objectStorageIncompleteDetail",
                action_target="object_storage",
                started_at=started_at,
            )
        task_health = _object_storage_task_health(session)
        try:
            health = BitifulObjectStorageProvider(
                config,
                connect_timeout_seconds=3,
                read_timeout_seconds=5,
                max_attempts=1,
            ).is_healthy()
        except Exception as exc:
            return _item(
                key="object_storage",
                status="failed",
                summary="对象存储配置无法初始化",
                summary_key="diagnostics.result.objectStorageInitFailed",
                detail=_safe_detail(exc, secrets=secrets),
                action_target="object_storage",
                started_at=started_at,
            )
        if not health.ok:
            return _item(
                key="object_storage",
                status="failed",
                summary="对象存储 Bucket 无法访问",
                summary_key="diagnostics.result.objectStorageUnavailable",
                detail=_safe_detail(health.summary, secrets=secrets),
                action_target="object_storage",
                started_at=started_at,
            )
        if task_health.failed_count:
            return _item(
                key="object_storage",
                status="failed",
                summary=f"有 {task_health.failed_count} 个对象存储同步任务重试失败",
                summary_key="diagnostics.result.objectStorageSyncFailures",
                summary_params={"count": task_health.failed_count},
                action_target="object_storage_sync",
                started_at=started_at,
            )
        if task_health.retrying_count:
            return _item(
                key="object_storage",
                status="warning",
                summary=f"有 {task_health.retrying_count} 个对象存储同步任务正在重试",
                summary_key="diagnostics.result.objectStorageSyncRetrying",
                summary_params={"count": task_health.retrying_count},
                action_target="object_storage_sync",
                started_at=started_at,
            )
    return _item(
        key="object_storage",
        status="healthy",
        summary="对象存储 Bucket 访问正常",
        summary_key="diagnostics.result.objectStorageHealthy",
        action_target="object_storage",
        started_at=started_at,
    )


def check_proxy() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    with get_session_factory()() as session:
        config = get_outbound_proxy_config(session)
        if config.proxy_port is None and not (config.webhook_enabled or config.oauth_enabled):
            return _item(
                key="proxy",
                status="skipped",
                summary="出站代理未配置",
                summary_key="diagnostics.result.proxyNotConfigured",
                action_target="proxy",
                started_at=started_at,
            )
        if config.proxy_port is None:
            return _item(
                key="proxy",
                status="failed",
                summary="出站代理缺少端口配置",
                summary_key="diagnostics.result.proxyPortMissing",
                action_target="proxy",
                started_at=started_at,
            )
        health = run_outbound_proxy_test(session, diagnostic=True)
    return _item(
        key="proxy",
        status="healthy" if health.ok else "failed",
        summary="出站代理转发正常" if health.ok else "出站代理无法完成 HTTPS 请求",
        summary_key=("diagnostics.result.proxyHealthy" if health.ok else "diagnostics.result.proxyFailed"),
        detail=_safe_detail(health.summary),
        action_target="proxy",
        started_at=started_at,
    )


def _backup_payload(config) -> BackupSyncConfigUpdate:
    return BackupSyncConfigUpdate(
        enabled=config.enabled,
        paused=config.paused,
        interval_minutes=config.interval_minutes,
        transport_mode=config.transport_mode,
        site_slug=config.site_slug,
        remote_host=config.transport.remote_host,
        remote_port=config.transport.remote_port,
        remote_path=config.transport.remote_path,
        remote_username=config.transport.remote_username,
        credential_ref=config.credential_ref,
        encrypt_runtime_data=config.encrypt_runtime_data,
        max_retries=config.max_retries,
        retry_backoff_seconds=config.retry_backoff_seconds,
        max_retention_count=config.max_retention_count,
        retention_days=config.retention_days,
    )


def check_backup() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    now = utcnow()
    with get_session_factory()() as session:
        config = get_backup_sync_config(session)
        if not config.enabled:
            return _item(
                key="backup",
                status="skipped",
                summary="远程备份未启用",
                summary_key="diagnostics.result.backupDisabled",
                action_target="backup_settings",
                started_at=started_at,
            )
        if config.paused:
            return _item(
                key="backup",
                status="skipped",
                summary="远程备份已暂停",
                summary_key="diagnostics.result.backupPaused",
                action_target="backup_settings",
                started_at=started_at,
            )

        payload = _backup_payload(config)
        last_synced_at = (
            normalize_shanghai_datetime(config.last_synced_at) if config.last_synced_at is not None else None
        )
        freshness_minutes = max(config.interval_minutes * 2, BACKUP_MINIMUM_FRESHNESS_MINUTES)
        is_stale = last_synced_at is None or now - last_synced_at > timedelta(minutes=freshness_minutes)
        should_probe_write = bool(is_stale or config.last_error)
        latest_queue_item = _latest_backup_queue_item(session)

        try:
            probe = probe_backup_machine_connection(session, payload)
        except Exception as exc:
            return _item(
                key="backup",
                status="failed",
                summary="备份配置无法完成连接检查",
                summary_key="diagnostics.result.backupProbeFailed",
                detail=_safe_detail(exc),
                action_target="backup_settings",
                started_at=started_at,
            )
        if not probe.ok:
            return _item(
                key="backup",
                status="failed",
                summary="备份机无法连接",
                summary_key="diagnostics.result.backupUnavailable",
                detail=_safe_detail(probe.summary),
                action_target="backup_settings",
                started_at=started_at,
            )
        if probe.remote_history_state == "foreign":
            return _item(
                key="backup",
                status="failed",
                summary="备份机上存在另一套站点历史",
                summary_key="diagnostics.result.backupForeignHistory",
                detail=_safe_detail(probe.remote_history_summary),
                action_target="backup_settings",
                started_at=started_at,
            )
        if not probe.recovery_key_ready or not probe.recovery_key_acknowledged:
            return _item(
                key="backup",
                status="failed",
                summary="备份恢复密钥尚未准备完成",
                summary_key="diagnostics.result.backupRecoveryKeyMissing",
                detail="请生成、保存并确认恢复密钥后再启用自动备份。",
                detail_key="diagnostics.result.backupRecoveryKeyMissingDetail",
                action_target="backup_settings",
                started_at=started_at,
            )
        if should_probe_write:
            write_probe = probe_backup_write_access(session, payload)
            if not write_probe.ok:
                return _item(
                    key="backup",
                    status="failed",
                    summary="备份机远端目录无法写入",
                    summary_key="diagnostics.result.backupWriteUnavailable",
                    detail=_safe_detail(write_probe.summary),
                    action_target="backup_settings",
                    started_at=started_at,
                )
        if latest_queue_item is not None and latest_queue_item.status == "failed":
            return _item(
                key="backup",
                status="failed",
                summary="最近一次备份任务已耗尽重试次数",
                summary_key="diagnostics.result.backupTaskFailed",
                detail=_safe_detail(latest_queue_item.last_error or config.last_error),
                action_target="backup_runs",
                started_at=started_at,
            )
        if (
            latest_queue_item is not None
            and latest_queue_item.status in {"queued", "running", "retrying"}
            and (latest_queue_item.retry_count > 0 or config.last_error)
        ):
            return _item(
                key="backup",
                status="warning",
                summary="备份任务正在自动重试",
                summary_key="diagnostics.result.backupRetrying",
                detail=_safe_detail(latest_queue_item.last_error or config.last_error),
                action_target="backup_runs",
                started_at=started_at,
            )
        if config.last_error:
            return _item(
                key="backup",
                status="warning",
                summary="最近一次备份任务发生错误",
                summary_key="diagnostics.result.backupLastError",
                detail=_safe_detail(config.last_error),
                action_target="backup_runs",
                started_at=started_at,
            )
        if is_stale:
            return _item(
                key="backup",
                status="warning",
                summary="最近成功备份已经超过预期时间",
                summary_key="diagnostics.result.backupStale",
                detail="连接和写入检查正常，可以前往备份记录确认任务调度。",
                detail_key="diagnostics.result.backupStaleDetail",
                action_target="backup_runs",
                started_at=started_at,
            )
    return _item(
        key="backup",
        status="healthy",
        summary="备份机连接正常，最近备份时间符合预期",
        summary_key="diagnostics.result.backupHealthy",
        action_target="backup_settings",
        started_at=started_at,
    )


def check_mcp() -> SystemDiagnosticItemRead:
    started_at = time.perf_counter()
    with get_session_factory()() as session:
        if not mcp_public_access_enabled(session):
            return _item(
                key="mcp",
                status="skipped",
                summary="MCP 服务未启用",
                summary_key="diagnostics.result.mcpDisabled",
                action_target="mcp",
                started_at=started_at,
            )
        capabilities = list_registered_mcp_capabilities()
        if not capabilities:
            return _item(
                key="mcp",
                status="failed",
                summary="MCP 能力注册表为空",
                summary_key="diagnostics.result.mcpRegistryEmpty",
                action_target="mcp",
                started_at=started_at,
            )
        keys = list(session.scalars(select(ApiKey).where(ApiKey.enabled.is_(True))).all())
        connect_keys = [key for key in keys if AGENT_CONNECT in list(key.scopes or [])]
        if not connect_keys:
            return _item(
                key="mcp",
                status="failed",
                summary="MCP 缺少启用且具有连接权限的 API Key",
                summary_key="diagnostics.result.mcpConnectKeyMissing",
                action_target="mcp",
                started_at=started_at,
            )
        usable_capability_count = max(
            (len(filter_capabilities_for_scopes(capabilities, list(key.scopes or []))) for key in connect_keys),
            default=0,
        )
        if usable_capability_count == 0:
            return _item(
                key="mcp",
                status="failed",
                summary="MCP API Key 没有可用的能力权限",
                summary_key="diagnostics.result.mcpCapabilityMissing",
                action_target="mcp",
                started_at=started_at,
            )
    return _item(
        key="mcp",
        status="healthy",
        summary="MCP 配置与能力权限已就绪",
        summary_key="diagnostics.result.mcpHealthy",
        detail=f"当前至少有 {usable_capability_count} 项能力可用。",
        detail_key="diagnostics.result.mcpCapabilityCountDetail",
        detail_params={"count": usable_capability_count},
        action_target="mcp",
        started_at=started_at,
    )


def _default_definitions() -> tuple[DiagnosticCheckDefinition, ...]:
    return (
        DiagnosticCheckDefinition("database", "system", check_database),
        DiagnosticCheckDefinition("storage", "system", check_storage),
        DiagnosticCheckDefinition("model_api", "model_api", check_model_api),
        DiagnosticCheckDefinition("smtp", "smtp", check_smtp),
        DiagnosticCheckDefinition("object_storage", "object_storage", check_object_storage),
        DiagnosticCheckDefinition("proxy", "proxy", check_proxy),
        DiagnosticCheckDefinition("backup", "backup_settings", check_backup),
        DiagnosticCheckDefinition("mcp", "mcp", check_mcp),
    )


def collect_system_diagnostics(
    *,
    definitions: Sequence[DiagnosticCheckDefinition] | None = None,
) -> DiagnosticSummary:
    items: list[SystemDiagnosticItemRead] = []
    for definition in definitions or _default_definitions():
        started_at = time.perf_counter()
        try:
            item = definition.checker()
        except Exception as exc:
            logger.warning(
                "System diagnostic check failed: %s (%s)",
                definition.key,
                type(exc).__name__,
            )
            item = _item(
                key=definition.key,
                status="failed",
                summary="检查过程中出现异常",
                summary_key="diagnostics.result.checkUnexpected",
                detail="请打开对应设置核对配置后重试。",
                detail_key="diagnostics.result.checkUnexpectedDetail",
                action_target=definition.action_target,
                started_at=started_at,
            )
        items.append(item)
    return aggregate_diagnostic_items(items)


_OBJECT_STORAGE_TASK_RESULT_KEYS = {
    "diagnostics.result.objectStorageSyncFailures",
    "diagnostics.result.objectStorageSyncRetrying",
}
_BACKUP_TASK_RESULT_KEYS = {
    "diagnostics.result.backupLastError",
    "diagnostics.result.backupRetrying",
    "diagnostics.result.backupTaskFailed",
    "diagnostics.result.backupStale",
}


def _replace_operational_item(
    item: SystemDiagnosticItemRead,
    *,
    status: Literal["healthy", "warning", "failed", "skipped"],
    summary: str,
    summary_key: str,
    action_target: DiagnosticActionTarget,
    checked_at: datetime,
    summary_params: dict[str, str | int] | None = None,
    detail: str | None = None,
) -> SystemDiagnosticItemRead:
    return item.model_copy(
        update={
            "status": status,
            "summary": summary,
            "summary_key": summary_key,
            "summary_params": summary_params or {},
            "detail": detail,
            "detail_key": None,
            "detail_params": {},
            "action_target": action_target,
            "checked_at": checked_at,
        }
    )


def _is_newer(candidate: datetime | None, reference: datetime | None) -> bool:
    if candidate is None:
        return False
    if reference is None:
        return True
    return normalize_shanghai_datetime(candidate) > normalize_shanghai_datetime(reference)


def _reconcile_object_storage_item(
    session,
    item: SystemDiagnosticItemRead,
    *,
    now: datetime,
) -> SystemDiagnosticItemRead:
    config = session.scalars(select(ObjectStorageConfig).limit(1)).first()
    if config is None or not config.enabled:
        return _replace_operational_item(
            item,
            status="skipped",
            summary="对象存储未启用",
            summary_key="diagnostics.result.objectStorageDisabled",
            action_target="object_storage",
            checked_at=now,
        )
    if item.status == "failed" and item.summary_key not in _OBJECT_STORAGE_TASK_RESULT_KEYS:
        return item

    task_health = _object_storage_task_health(session)
    if task_health.failed_count:
        return _replace_operational_item(
            item,
            status="failed",
            summary=f"有 {task_health.failed_count} 个对象存储同步任务重试失败",
            summary_key="diagnostics.result.objectStorageSyncFailures",
            summary_params={"count": task_health.failed_count},
            action_target="object_storage_sync",
            checked_at=now,
        )
    if task_health.retrying_count:
        return _replace_operational_item(
            item,
            status="warning",
            summary=f"有 {task_health.retrying_count} 个对象存储同步任务正在重试",
            summary_key="diagnostics.result.objectStorageSyncRetrying",
            summary_params={"count": task_health.retrying_count},
            action_target="object_storage_sync",
            checked_at=now,
        )
    if item.summary_key in _OBJECT_STORAGE_TASK_RESULT_KEYS and _is_newer(
        task_health.latest_completed_at,
        item.checked_at,
    ):
        return _replace_operational_item(
            item,
            status="healthy",
            summary="对象存储 Bucket 访问正常",
            summary_key="diagnostics.result.objectStorageHealthy",
            action_target="object_storage",
            checked_at=task_health.latest_completed_at or now,
        )
    return item


def _latest_backup_queue_item(session) -> BackupQueueItem | None:
    return session.scalars(
        select(BackupQueueItem)
        .order_by(
            BackupQueueItem.updated_at.desc(),
            BackupQueueItem.created_at.desc(),
            BackupQueueItem.id.desc(),
        )
        .limit(1)
    ).first()


def _reconcile_backup_item(
    session,
    item: SystemDiagnosticItemRead,
    *,
    now: datetime,
) -> SystemDiagnosticItemRead:
    config = session.scalars(select(BackupTargetConfig).limit(1)).first()
    if config is None:
        return item
    if not config.enabled:
        return _replace_operational_item(
            item,
            status="skipped",
            summary="远程备份未启用",
            summary_key="diagnostics.result.backupDisabled",
            action_target="backup_settings",
            checked_at=now,
        )
    if config.paused:
        return _replace_operational_item(
            item,
            status="skipped",
            summary="远程备份已暂停",
            summary_key="diagnostics.result.backupPaused",
            action_target="backup_settings",
            checked_at=now,
        )
    if item.status == "failed" and item.summary_key not in _BACKUP_TASK_RESULT_KEYS:
        return item

    latest_queue_item = _latest_backup_queue_item(session)
    if latest_queue_item is not None and latest_queue_item.status == "failed":
        return _replace_operational_item(
            item,
            status="failed",
            summary="最近一次备份任务已耗尽重试次数",
            summary_key="diagnostics.result.backupTaskFailed",
            detail=_safe_detail(latest_queue_item.last_error or config.last_error),
            action_target="backup_runs",
            checked_at=now,
        )
    if (
        latest_queue_item is not None
        and latest_queue_item.status in {"queued", "running", "retrying"}
        and (latest_queue_item.retry_count > 0 or config.last_error)
    ):
        return _replace_operational_item(
            item,
            status="warning",
            summary="备份任务正在自动重试",
            summary_key="diagnostics.result.backupRetrying",
            detail=_safe_detail(latest_queue_item.last_error or config.last_error),
            action_target="backup_runs",
            checked_at=now,
        )

    last_synced_at = normalize_shanghai_datetime(config.last_synced_at) if config.last_synced_at is not None else None
    if _is_newer(last_synced_at, item.checked_at):
        return _replace_operational_item(
            item,
            status="healthy",
            summary="备份机连接正常，最近备份时间符合预期",
            summary_key="diagnostics.result.backupHealthy",
            action_target="backup_settings",
            checked_at=last_synced_at or now,
        )
    if config.last_error and item.summary_key not in _BACKUP_TASK_RESULT_KEYS:
        return _replace_operational_item(
            item,
            status="failed",
            summary="最近一次备份任务已失败",
            summary_key="diagnostics.result.backupTaskFailed",
            detail=_safe_detail(config.last_error),
            action_target="backup_runs",
            checked_at=now,
        )
    return item


def _deserialize_diagnostic_items(state) -> list[SystemDiagnosticItemRead]:
    items: list[SystemDiagnosticItemRead] = []
    for payload in state.results_json or []:
        try:
            items.append(SystemDiagnosticItemRead.model_validate(payload))
        except (TypeError, ValueError):
            logger.warning("Ignoring an invalid persisted system diagnostic item")
    return items


def _reconcile_operational_items(
    session,
    items: Sequence[SystemDiagnosticItemRead],
    *,
    now: datetime,
) -> list[SystemDiagnosticItemRead]:
    reconciled: list[SystemDiagnosticItemRead] = []
    for item in items:
        if item.key == "object_storage":
            reconciled.append(_reconcile_object_storage_item(session, item, now=now))
        elif item.key == "backup":
            reconciled.append(_reconcile_backup_item(session, item, now=now))
        else:
            reconciled.append(item)
    return reconciled


def _serialize_diagnostic_state(
    state,
    *,
    include_items: bool,
    now: datetime,
    items_override: Sequence[SystemDiagnosticItemRead] | None = None,
) -> SystemDiagnosticStateRead:
    if state is None:
        return SystemDiagnosticStateRead()

    started_at = normalize_shanghai_datetime(state.started_at) if state.started_at is not None else None
    completed_at = normalize_shanghai_datetime(state.completed_at) if state.completed_at is not None else None
    active = state.execution_status in {"queued", "running"}
    abandoned = bool(active and started_at is not None and started_at <= now - DIAGNOSTIC_RUN_ABANDONED_AFTER)
    stale = bool(completed_at is not None and completed_at <= now - DIAGNOSTIC_RESULT_STALE_AFTER)

    all_items = (
        list(items_override)
        if items_override is not None
        else (_deserialize_diagnostic_items(state) if include_items else [])
    )

    if abandoned and (include_items or items_override is not None):
        all_items.insert(
            0,
            SystemDiagnosticItemRead(
                key="diagnostic_runner",
                status="failed",
                summary="上一次诊断任务未能完成",
                summary_key="diagnostics.result.runnerAbandoned",
                detail="任务运行超过 10 分钟后已停止等待，请重新检查；若再次发生，请查看系统日志。",
                detail_key="diagnostics.result.runnerAbandonedDetail",
                action_target="system",
                checked_at=now,
            ),
        )

    recalculated_summary = aggregate_diagnostic_items(all_items) if items_override is not None and all_items else None
    overall_status = recalculated_summary.overall_status if recalculated_summary is not None else state.overall_status
    if overall_status not in {"unknown", "healthy", "attention"}:
        overall_status = "unknown"
    if stale or abandoned or state.last_error:
        overall_status = "attention"

    execution_status = state.execution_status
    if execution_status not in {"never", "queued", "running", "completed"}:
        execution_status = "never"
    trigger_kind = state.trigger_kind
    if trigger_kind not in {"manual", "scheduled", "startup"}:
        trigger_kind = None

    healthy_count = (
        recalculated_summary.healthy_count
        if recalculated_summary is not None
        else max(int(state.healthy_count or 0), 0)
    )
    warning_count = (
        recalculated_summary.warning_count
        if recalculated_summary is not None
        else max(int(state.warning_count or 0), 0)
    )
    failed_count = (
        recalculated_summary.failed_count
        if recalculated_summary is not None
        else max(int(state.failed_count or 0), 1 if abandoned else 0)
    )
    skipped_count = (
        recalculated_summary.skipped_count
        if recalculated_summary is not None
        else max(int(state.skipped_count or 0), 0)
    )
    issue_count = warning_count + failed_count
    if overall_status == "attention" and issue_count == 0:
        issue_count = 1

    return SystemDiagnosticStateRead(
        execution_status=execution_status,
        overall_status=overall_status,
        trigger_kind=trigger_kind,
        run_id=state.run_id,
        is_running=active and not abandoned,
        is_stale=stale,
        healthy_count=healthy_count,
        warning_count=warning_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        issue_count=issue_count,
        items=all_items if include_items else [],
        started_at=started_at,
        completed_at=completed_at,
        last_error=state.last_error,
        last_error_key=("diagnostics.result.runnerFailed" if state.last_error else None),
    )


def get_system_diagnostic_state(*, include_items: bool = True) -> SystemDiagnosticStateRead:
    now = utcnow()
    with get_session_factory()() as session:
        state = get_diagnostic_state(session)
        items_override: list[SystemDiagnosticItemRead] | None = None
        if state is not None and state.results_json:
            persisted_items = _deserialize_diagnostic_items(state)
            if persisted_items:
                items_override = _reconcile_operational_items(session, persisted_items, now=now)
        return _serialize_diagnostic_state(
            state,
            include_items=include_items,
            now=now,
            items_override=items_override,
        )


def queue_system_diagnostic_run(
    *,
    trigger_kind: DiagnosticTriggerKind,
    skip_if_completed_since: datetime | None = None,
) -> tuple[SystemDiagnosticStateRead, bool]:
    now = utcnow()
    with get_session_factory()() as session:
        state, queued = try_queue_diagnostic_run(
            session,
            trigger_kind=trigger_kind,
            now=now,
            skip_if_completed_since=skip_if_completed_since,
        )
        return _serialize_diagnostic_state(state, include_items=True, now=now), queued


def execute_system_diagnostic_run(run_id: str | None) -> bool:
    """Claim, execute, and persist a run while keeping network work outside DB sessions."""
    with get_session_factory()() as session:
        claimed = claim_diagnostic_run(session, run_id=run_id)
    if not claimed:
        return False

    try:
        summary = collect_system_diagnostics()
    except Exception as exc:
        logger.error(
            "Unexpected failure while collecting system diagnostics (%s)",
            type(exc).__name__,
        )
        failure_item = SystemDiagnosticItemRead(
            key="diagnostic_runner",
            status="failed",
            summary="诊断任务未能完成",
            summary_key="diagnostics.result.runnerFailed",
            detail="请稍后重试；如果问题持续存在，请检查系统日志与运行环境。",
            detail_key="diagnostics.result.runnerFailedDetail",
            action_target="system",
            checked_at=utcnow(),
        )
        with get_session_factory()() as session:
            complete_diagnostic_run(
                session,
                run_id=run_id,
                overall_status="attention",
                healthy_count=0,
                warning_count=0,
                failed_count=1,
                skipped_count=0,
                results=[failure_item.model_dump(mode="json")],
                last_error="诊断任务未能完成，请稍后重试。",
            )
        return False

    with get_session_factory()() as session:
        return complete_diagnostic_run(
            session,
            run_id=run_id,
            overall_status=summary.overall_status,
            healthy_count=summary.healthy_count,
            warning_count=summary.warning_count,
            failed_count=summary.failed_count,
            skipped_count=summary.skipped_count,
            results=[item.model_dump(mode="json") for item in summary.items],
        )


def run_system_diagnostics(*, trigger_kind: DiagnosticTriggerKind) -> SystemDiagnosticStateRead:
    state, queued = queue_system_diagnostic_run(trigger_kind=trigger_kind)
    if queued:
        execute_system_diagnostic_run(state.run_id)
    return get_system_diagnostic_state()


def run_scheduled_system_diagnostics() -> SystemDiagnosticStateRead:
    now = utcnow()
    daily_boundary = now.replace(hour=4, minute=20, second=0, microsecond=0)
    if now < daily_boundary:
        daily_boundary -= timedelta(days=1)
    state, queued = queue_system_diagnostic_run(
        trigger_kind="scheduled",
        skip_if_completed_since=daily_boundary,
    )
    if queued:
        execute_system_diagnostic_run(state.run_id)
    return get_system_diagnostic_state()


def run_system_diagnostics_if_stale() -> SystemDiagnosticStateRead:
    state = get_system_diagnostic_state(include_items=False)
    if state.is_running or (state.execution_status == "completed" and not state.is_stale):
        return state
    return run_system_diagnostics(trigger_kind="startup")
