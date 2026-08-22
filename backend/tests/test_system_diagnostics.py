from __future__ import annotations

import os
import threading
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from aerisun.api.admin.scopes import AGENT_CONNECT, CONTENT_READ
from aerisun.core.base import utcnow
from aerisun.core.db import get_session_factory
from aerisun.domain.automation.schemas import AgentModelConfigUpdate
from aerisun.domain.automation.settings import update_agent_model_config
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.iam.models import ApiKey
from aerisun.domain.media.models import Asset, AssetMirrorQueueItem
from aerisun.domain.media.object_storage import get_or_create_object_storage_config
from aerisun.domain.ops.backup_sync import get_or_create_backup_sync_config
from aerisun.domain.ops.diagnostic_schemas import SystemDiagnosticItemRead
from aerisun.domain.ops.diagnostics import (
    DiagnosticCheckDefinition,
    aggregate_diagnostic_items,
    check_backup,
    check_database,
    check_mcp,
    check_model_api,
    check_object_storage,
    check_proxy,
    check_service_forwards,
    check_smtp,
    check_storage,
    collect_system_diagnostics,
    execute_system_diagnostic_run,
    get_system_diagnostic_state,
    queue_system_diagnostic_run,
    run_scheduled_system_diagnostics,
    run_system_diagnostics_if_stale,
)
from aerisun.domain.ops.models import BackupQueueItem, SystemDiagnosticState
from aerisun.domain.ops.schemas import BackupSyncConfigTestRead
from aerisun.domain.outbound_proxy.schemas import OutboundProxyConfigUpdate
from aerisun.domain.outbound_proxy.service import update_outbound_proxy_config
from aerisun.domain.service_forwards.schemas import ServiceForwardRead
from aerisun.domain.site_config.models import SiteProfile
from aerisun.domain.subscription.service import get_subscription_config_orm


def _set_feature_flags(seeded_session, **updates: object) -> None:
    profile = seeded_session.query(SiteProfile).first()
    assert profile is not None
    flags = dict(profile.feature_flags or {})
    flags.update(updates)
    profile.feature_flags = flags
    seeded_session.commit()


def _persist_completed_diagnostic_snapshot(
    seeded_session,
    item: SystemDiagnosticItemRead,
    *,
    completed_at,
) -> None:
    summary = aggregate_diagnostic_items([item])
    seeded_session.add(
        SystemDiagnosticState(
            id="current",
            execution_status="completed",
            overall_status=summary.overall_status,
            trigger_kind="scheduled",
            healthy_count=summary.healthy_count,
            warning_count=summary.warning_count,
            failed_count=summary.failed_count,
            skipped_count=summary.skipped_count,
            results_json=[item.model_dump(mode="json")],
            started_at=completed_at,
            completed_at=completed_at,
        )
    )
    seeded_session.commit()


def _service_forward(
    route_id: str,
    *,
    name: str,
    source: str,
) -> ServiceForwardRead:
    return ServiceForwardRead(
        id=route_id,
        name=name,
        slug=route_id,
        path=f"/{route_id}",
        source=source,  # type: ignore[arg-type]
        target_url=f"http://127.0.0.1:{8000 + len(route_id)}",
        public_url=f"https://site.example/{route_id}",
    )


def test_aggregate_diagnostics_ignores_skipped_items_for_overall_health() -> None:
    summary = aggregate_diagnostic_items(
        [
            SystemDiagnosticItemRead(
                key="database",
                status="healthy",
                summary="数据库正常",
                action_target="system",
            ),
            SystemDiagnosticItemRead(
                key="model_api",
                status="skipped",
                summary="未启用",
                action_target="model_api",
            ),
        ]
    )

    assert summary.overall_status == "healthy"
    assert summary.healthy_count == 1
    assert summary.warning_count == 0
    assert summary.failed_count == 0
    assert summary.skipped_count == 1
    assert summary.issue_count == 0


def test_diagnostic_results_include_a_stable_translation_key() -> None:
    result = check_database()

    assert result.summary_key == "diagnostics.result.databaseHealthy"
    assert result.summary_params == {}


def test_service_forward_diagnostic_skips_when_no_rules_are_configured(monkeypatch) -> None:
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.list_service_forwards", lambda: [])

    result = check_service_forwards()

    assert result.status == "skipped"
    assert result.summary_key == "diagnostics.result.serviceForwardsDisabled"
    assert result.action_target == "service_forwards"


def test_service_forward_diagnostic_checks_every_source_and_aggregates_partial_failures(monkeypatch) -> None:
    import aerisun.domain.ops.diagnostics as diagnostics

    rules = [
        _service_forward("local-panel", name="本机面板", source="local"),
        _service_forward("embedding", name="Embedding 服务", source="tailscale"),
        _service_forward("legacy", name="旧规则", source="custom"),
    ]
    statuses = {"local-panel": "reachable", "embedding": "unreachable", "legacy": "reachable"}
    calls: list[str] = []

    def fake_probe(route_id: str):
        calls.append(route_id)
        route = next(rule for rule in rules if rule.id == route_id)
        return route.model_copy(update={"status": statuses[route_id]})

    monkeypatch.setattr(diagnostics, "list_service_forwards", lambda: rules)
    monkeypatch.setattr(diagnostics, "test_service_forward", fake_probe)

    result = check_service_forwards()

    assert sorted(calls) == ["embedding", "legacy", "local-panel"]
    assert result.status == "warning"
    assert result.summary_key == "diagnostics.result.serviceForwardsDegraded"
    assert result.summary_params == {"count": 1}
    assert result.detail == "Embedding 服务"
    assert result.action_target == "service_forwards"


def test_service_forward_diagnostic_limits_concurrent_probes_and_reports_healthy(monkeypatch) -> None:
    import aerisun.domain.ops.diagnostics as diagnostics

    rules = [_service_forward(f"service-{index}", name=f"服务 {index}", source="local") for index in range(5)]
    lock = threading.Lock()
    four_probes_started = threading.Event()
    active_probes = 0
    peak_concurrent_probes = 0

    def fake_probe(route_id: str) -> ServiceForwardRead:
        nonlocal active_probes, peak_concurrent_probes
        with lock:
            active_probes += 1
            peak_concurrent_probes = max(peak_concurrent_probes, active_probes)
            if active_probes == 4:
                four_probes_started.set()
        assert four_probes_started.wait(timeout=1)
        with lock:
            active_probes -= 1
        return next(rule for rule in rules if rule.id == route_id).model_copy(update={"status": "reachable"})

    monkeypatch.setattr(diagnostics, "list_service_forwards", lambda: rules)
    monkeypatch.setattr(diagnostics, "test_service_forward", fake_probe)

    result = check_service_forwards()

    assert peak_concurrent_probes == 4
    assert result.status == "healthy"
    assert result.summary_key == "diagnostics.result.serviceForwardsHealthy"
    assert result.summary_params == {"count": 5}


def test_service_forward_diagnostic_fails_when_every_rule_is_unreachable(monkeypatch) -> None:
    import aerisun.domain.ops.diagnostics as diagnostics

    rules = [
        _service_forward("first", name="第一个服务", source="local"),
        _service_forward("second", name="第二个服务", source="tailscale"),
    ]
    monkeypatch.setattr(diagnostics, "list_service_forwards", lambda: rules)
    monkeypatch.setattr(
        diagnostics,
        "test_service_forward",
        lambda route_id: next(rule for rule in rules if rule.id == route_id).model_copy(
            update={"status": "unreachable"}
        ),
    )

    result = check_service_forwards()

    assert result.status == "failed"
    assert result.summary_key == "diagnostics.result.serviceForwardsUnavailable"
    assert result.summary_params == {"count": 2}
    assert result.detail == "第一个服务；第二个服务"


def test_collector_isolates_failures_without_persisting_or_logging_raw_exception_text(
    caplog,
) -> None:
    def fail_check() -> SystemDiagnosticItemRead:
        raise RuntimeError("request failed with api-key-super-secret")

    def healthy_check() -> SystemDiagnosticItemRead:
        return SystemDiagnosticItemRead(
            key="storage",
            status="healthy",
            summary="存储正常",
            action_target="system",
        )

    summary = collect_system_diagnostics(
        definitions=[
            DiagnosticCheckDefinition("model_api", "model_api", fail_check),
            DiagnosticCheckDefinition("storage", "system", healthy_check),
        ]
    )

    assert [item.status for item in summary.items] == ["failed", "healthy"]
    assert summary.overall_status == "attention"
    assert "api-key-super-secret" not in str(summary.items[0].model_dump())
    assert "api-key-super-secret" not in caplog.text


def test_disabled_integrations_are_skipped_without_network_calls(seeded_session, monkeypatch) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(enabled=False, base_url="", model="", api_key=""),
    )
    subscription = get_subscription_config_orm(seeded_session)
    subscription.enabled = False
    subscription.comment_feedback_enabled = False
    subscription.smtp_test_passed = False
    object_storage = get_or_create_object_storage_config(seeded_session)
    object_storage.enabled = False
    backup = get_or_create_backup_sync_config(seeded_session)
    backup.enabled = False
    backup.paused = False
    seeded_session.commit()
    _set_feature_flags(
        seeded_session,
        outbound_proxy_config={
            "proxy_port": None,
            "webhook_enabled": False,
            "oauth_enabled": False,
        },
        mcp_public_access=False,
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("disabled integrations must not perform network probes")

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_model_config", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.send_subscription_smtp_diagnostic_email", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.BitifulObjectStorageProvider", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.run_outbound_proxy_test", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_machine_connection", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_write_access", forbidden)

    summary = collect_system_diagnostics()
    by_key = {item.key: item for item in summary.items}

    for key in ("model_api", "smtp", "object_storage", "proxy", "backup", "mcp"):
        assert by_key[key].status == "skipped"
    assert summary.overall_status == "healthy"


def test_configured_proxy_is_checked_even_when_no_proxy_scope_is_enabled(
    seeded_session,
    monkeypatch,
) -> None:
    _set_feature_flags(
        seeded_session,
        outbound_proxy_config={
            "proxy_port": 7890,
            "webhook_enabled": False,
            "oauth_enabled": False,
        },
    )
    calls = 0

    def successful_probe(_session, *, diagnostic: bool):
        nonlocal calls
        calls += 1
        assert diagnostic is True
        return SimpleNamespace(ok=True, summary="代理端口连通")

    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.run_outbound_proxy_test",
        successful_probe,
    )

    result = check_proxy()

    assert calls == 1
    assert result.status == "healthy"
    assert result.summary_key == "diagnostics.result.proxyHealthy"


def test_disabled_email_features_skip_a_previously_tested_smtp_config(
    seeded_session,
    monkeypatch,
) -> None:
    config = get_subscription_config_orm(seeded_session)
    config.enabled = False
    config.comment_feedback_enabled = False
    config.smtp_test_passed = True
    seeded_session.commit()

    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.send_subscription_smtp_diagnostic_email",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disabled email features must not send an SMTP test message")
        ),
    )

    result = check_smtp()

    assert result.status == "skipped"
    assert result.summary_key == "diagnostics.result.smtpDisabled"


def test_model_api_diagnostic_caps_timeout_and_calls_the_provider_once(seeded_session, monkeypatch) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=True,
            base_url="https://models.example.com/v1",
            model="small-model",
            api_key="model-secret",
            timeout_seconds=300,
        ),
    )
    captured: list[dict[str, object]] = []

    def fake_probe(config: dict[str, object]) -> dict[str, str]:
        captured.append(config)
        return {
            "model": "small-model",
            "endpoint": "https://models.example.com/v1/chat/completions",
            "summary": "connection_ok",
        }

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_model_config", fake_probe)

    result = check_model_api()

    assert result.status == "healthy"
    assert len(captured) == 1
    assert captured[0]["timeout_seconds"] == 15
    assert "model-secret" not in str(result.model_dump())


def test_model_diagnostic_warns_when_one_enabled_source_is_unavailable(seeded_session, monkeypatch) -> None:
    update_outbound_proxy_config(
        seeded_session,
        OutboundProxyConfigUpdate(proxy_port=7890, oauth_enabled=True),
    )
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate.model_validate(
            {
                "primary_source": "chatgpt_oauth",
                "chatgpt_oauth": {"enabled": True, "model": "gpt-5.2-codex"},
                "openai_compatible": {
                    "enabled": True,
                    "base_url": "https://models.example.com/v1",
                    "model": "fallback-model",
                    "api_key": "model-secret",
                },
            }
        ),
    )
    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.probe_chatgpt_config",
        lambda config: {"model": config["model"], "summary": "connection_ok"},
    )
    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.probe_model_config",
        lambda config: (_ for _ in ()).throw(ValidationError("fallback offline")),
    )

    result = check_model_api()

    assert result.status == "warning"
    assert result.summary_key == "diagnostics.result.modelDegraded"
    assert "model-secret" not in str(result.model_dump())


def test_storage_diagnostic_checks_every_directory_and_each_unique_filesystem(
    tmp_path,
    monkeypatch,
) -> None:
    paths = tuple(tmp_path / name for name in ("data", "media", "secrets", "backup-tmp"))
    for path in paths:
        path.mkdir()

    settings = SimpleNamespace(
        data_dir=paths[0],
        media_dir=paths[1],
        secrets_dir=paths[2],
        backup_sync_tmp_dir=paths[3],
        store_dir=paths[0],
    )
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.get_settings", lambda: settings)

    real_stat = Path.stat
    devices = {paths[0]: 101, paths[1]: 101, paths[2]: 202, paths[3]: 202}

    def fake_stat(path: Path, *, follow_symlinks: bool = True):
        result = real_stat(path, follow_symlinks=follow_symlinks)
        values = list(result)
        values[2] = devices.get(path, result.st_dev)
        return os.stat_result(values)

    monkeypatch.setattr(Path, "stat", fake_stat)

    written_paths: list[Path] = []

    class FakeTemporaryFile:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def write(self, _payload: bytes) -> None:
            return None

        def flush(self) -> None:
            return None

    def fake_temporary_file(*, dir, **_kwargs):
        written_paths.append(Path(dir))
        return FakeTemporaryFile()

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.tempfile.NamedTemporaryFile", fake_temporary_file)

    disk_paths: list[Path] = []

    def fake_disk_usage(path):
        path = Path(path)
        disk_paths.append(path)
        if path == paths[2]:
            return SimpleNamespace(total=100 * 1024**3, used=99 * 1024**3, free=1 * 1024**3)
        return SimpleNamespace(total=100 * 1024**3, used=50 * 1024**3, free=50 * 1024**3)

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.shutil.disk_usage", fake_disk_usage)

    result = check_storage()

    assert written_paths == list(paths)
    assert disk_paths == [paths[0], paths[2]]
    assert result.status == "warning", result.detail
    assert "1.0 GB" in (result.detail or "")


def test_object_storage_diagnostic_ignores_a_resolved_historical_queue_failure(
    seeded_session,
    monkeypatch,
) -> None:
    config = get_or_create_object_storage_config(seeded_session)
    config.enabled = True
    config.endpoint = "https://s3.example.com"
    config.bucket = "serino"
    config.access_key = "access"
    config.secret_key = "secret"
    asset = Asset(
        file_name="resolved.webp",
        resource_key="assets/resolved.webp",
        visibility="internal",
        scope="user",
        category="general",
        storage_path="/tmp/resolved.webp",
        storage_provider="bitiful",
        remote_status="available",
        mirror_status="completed",
    )
    seeded_session.add(asset)
    seeded_session.flush()
    seeded_session.add_all(
        [
            AssetMirrorQueueItem(
                asset_id=asset.id,
                object_key="assets/resolved.webp",
                status="failed",
                next_retry_at=utcnow() - timedelta(minutes=2),
            ),
            AssetMirrorQueueItem(
                asset_id=asset.id,
                object_key="assets/resolved.webp",
                status="completed",
                next_retry_at=utcnow() - timedelta(minutes=1),
            ),
        ]
    )
    seeded_session.commit()

    class HealthyProvider:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def is_healthy(self):
            return SimpleNamespace(ok=True, summary="healthy")

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.BitifulObjectStorageProvider", HealthyProvider)

    result = check_object_storage()

    assert result.status == "healthy"


def test_object_storage_diagnostic_warns_while_failed_sync_is_retrying(
    seeded_session,
    monkeypatch,
) -> None:
    config = get_or_create_object_storage_config(seeded_session)
    config.enabled = True
    config.endpoint = "https://s3.example.com"
    config.bucket = "serino"
    config.access_key = "access"
    config.secret_key = "secret"
    asset = Asset(
        file_name="retrying.webp",
        resource_key="assets/retrying.webp",
        visibility="internal",
        scope="user",
        category="general",
        storage_path="/tmp/retrying.webp",
        storage_provider="bitiful",
        remote_status="available",
        mirror_status="retrying",
    )
    seeded_session.add(asset)
    seeded_session.flush()
    seeded_session.add(
        AssetMirrorQueueItem(
            asset_id=asset.id,
            object_key="assets/retrying.webp",
            status="retrying",
            retry_count=1,
            next_retry_at=utcnow() + timedelta(minutes=1),
            last_error="temporary upload failure",
        )
    )
    seeded_session.commit()

    class HealthyProvider:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def is_healthy(self):
            return SimpleNamespace(ok=True, summary="healthy")

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.BitifulObjectStorageProvider", HealthyProvider)

    result = check_object_storage()

    assert result.status == "warning"
    assert result.summary_key == "diagnostics.result.objectStorageSyncRetrying"
    assert result.action_target == "object_storage_sync"


def test_object_storage_diagnostic_fails_after_sync_retries_are_exhausted(
    seeded_session,
    monkeypatch,
) -> None:
    config = get_or_create_object_storage_config(seeded_session)
    config.enabled = True
    config.endpoint = "https://s3.example.com"
    config.bucket = "serino"
    config.access_key = "access"
    config.secret_key = "secret"
    seeded_session.add(
        Asset(
            file_name="failed.webp",
            resource_key="assets/failed.webp",
            visibility="internal",
            scope="user",
            category="general",
            storage_path="/tmp/failed.webp",
            storage_provider="bitiful",
            remote_status="failed",
            mirror_status="failed",
            mirror_last_error="upload retries exhausted",
        )
    )
    seeded_session.commit()

    class HealthyProvider:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def is_healthy(self):
            return SimpleNamespace(ok=True, summary="healthy")

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.BitifulObjectStorageProvider", HealthyProvider)

    result = check_object_storage()

    assert result.status == "failed"
    assert result.summary_key == "diagnostics.result.objectStorageSyncFailures"
    assert result.action_target == "object_storage_sync"


def test_smtp_diagnostic_does_not_overwrite_a_concurrent_admin_token_update(
    seeded_session,
    monkeypatch,
) -> None:
    config = get_subscription_config_orm(seeded_session)
    config.enabled = True
    config.smtp_auth_mode = "microsoft_oauth2"
    config.smtp_host = "smtp.office365.com"
    config.smtp_port = 587
    config.smtp_username = "mailer@example.com"
    config.smtp_oauth_tenant = "tenant"
    config.smtp_oauth_client_id = "old-client"
    config.smtp_oauth_client_secret = "old-secret"
    config.smtp_oauth_refresh_token = "old-refresh-token"
    config.smtp_from_email = "mailer@example.com"
    config.smtp_use_tls = True
    config.smtp_use_ssl = False
    config_id = config.id
    seeded_session.commit()

    def send_test(probe_config, *, timeout_seconds: int):
        assert timeout_seconds == 10
        assert probe_config is not config
        assert not hasattr(probe_config, "_sa_instance_state")
        probe_config.smtp_oauth_refresh_token = "rotated-old-refresh-token"
        with get_session_factory()() as concurrent_session:
            concurrent_config = concurrent_session.get(type(config), config_id)
            assert concurrent_config is not None
            concurrent_config.smtp_oauth_client_id = "new-client"
            concurrent_config.smtp_oauth_refresh_token = "admin-new-refresh-token"
            concurrent_session.commit()
        with get_session_factory()() as verification_session:
            concurrent_config = verification_session.get(type(config), config_id)
            assert concurrent_config is not None
            assert concurrent_config.smtp_oauth_refresh_token == "admin-new-refresh-token"
        return SimpleNamespace(recipient="do-not-reply@course.pku.edu.cn")

    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.send_subscription_smtp_diagnostic_email",
        send_test,
    )

    result = check_smtp()

    assert result.status == "warning", result.detail
    seeded_session.expire_all()
    persisted = seeded_session.get(type(config), config_id)
    assert persisted is not None
    assert persisted.smtp_oauth_refresh_token == "admin-new-refresh-token"
    assert persisted.smtp_oauth_client_id == "new-client"
    assert result.action_target == "smtp"


def test_smtp_diagnostic_reports_the_test_email_recipient(
    seeded_session,
    monkeypatch,
) -> None:
    config = get_subscription_config_orm(seeded_session)
    config.enabled = True
    config.smtp_host = "smtp.example.com"
    config.smtp_port = 587
    config.smtp_username = "mailer@example.com"
    config.smtp_password = "secret"
    config.smtp_from_email = "mailer@example.com"
    config.smtp_use_tls = True
    config.smtp_use_ssl = False
    seeded_session.commit()
    calls = 0

    def send_test(_config, *, timeout_seconds: int):
        nonlocal calls
        calls += 1
        assert timeout_seconds == 10
        return SimpleNamespace(recipient="diagnostics@example.com")

    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.send_subscription_smtp_diagnostic_email",
        send_test,
    )

    result = check_smtp()

    assert calls == 1
    assert result.status == "healthy"
    assert result.summary == "SMTP 测试邮件成功发送"
    assert result.summary_key == "diagnostics.result.smtpHealthy"
    assert result.detail is None
    assert result.detail_key is None
    assert result.detail_params == {}


def test_backup_diagnostic_uses_read_only_probe_after_a_recent_success(seeded_session, monkeypatch) -> None:
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.remote_host = "backup.example.com"
    config.remote_port = 22
    config.remote_path = "/srv/serino-backups"
    config.remote_username = "serino-backup"
    config.credential_ref = "default"
    config.interval_minutes = 60
    config.last_synced_at = utcnow()
    config.last_error = None
    seeded_session.commit()

    def quick_probe(*_args, **_kwargs) -> BackupSyncConfigTestRead:
        return BackupSyncConfigTestRead(
            ok=True,
            summary="备份机可连接",
            latency_ms=4,
            remote_path_preview="/srv/serino-backups",
            recovery_key_ready=True,
            recovery_key_acknowledged=True,
            remote_history_state="current",
            remote_history_summary="当前站点备份历史正常",
        )

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_machine_connection", quick_probe)
    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.probe_backup_write_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("recent successful backups do not need a daily write probe")
        ),
    )

    result = check_backup()

    assert result.status == "healthy"
    assert result.action_target == "backup_settings"


def test_backup_diagnostic_ignores_a_failed_queue_item_after_a_newer_success(
    seeded_session,
    monkeypatch,
) -> None:
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.remote_host = "backup.example.com"
    config.remote_port = 22
    config.remote_path = "/srv/serino-backups"
    config.remote_username = "serino-backup"
    config.credential_ref = "default"
    config.interval_minutes = 60
    config.last_synced_at = utcnow()
    config.last_error = None
    seeded_session.add_all(
        [
            BackupQueueItem(
                transport="sftp",
                trigger_kind="scheduled",
                status="failed",
                next_retry_at=utcnow() - timedelta(minutes=2),
            ),
            BackupQueueItem(
                transport="sftp",
                trigger_kind="scheduled",
                status="completed",
                next_retry_at=utcnow() - timedelta(minutes=1),
            ),
        ]
    )
    seeded_session.commit()

    monkeypatch.setattr(
        "aerisun.domain.ops.diagnostics.probe_backup_machine_connection",
        lambda *_args, **_kwargs: BackupSyncConfigTestRead(
            ok=True,
            summary="备份机可连接",
            latency_ms=4,
            remote_path_preview="/srv/serino-backups",
            recovery_key_ready=True,
            recovery_key_acknowledged=True,
            remote_history_state="current",
            remote_history_summary="当前站点备份历史正常",
        ),
    )

    result = check_backup()

    assert result.status == "healthy"


def test_backup_diagnostic_warns_during_automatic_retry(seeded_session, monkeypatch) -> None:
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.remote_host = "backup.example.com"
    config.remote_port = 22
    config.remote_path = "/srv/serino-backups"
    config.remote_username = "serino-backup"
    config.credential_ref = "default"
    config.interval_minutes = 60
    config.last_synced_at = utcnow()
    config.last_error = "temporary backup failure"
    seeded_session.add(
        BackupQueueItem(
            transport="sftp",
            trigger_kind="scheduled",
            status="retrying",
            retry_count=1,
            next_retry_at=utcnow() + timedelta(minutes=1),
            last_error="temporary backup failure",
        )
    )
    seeded_session.commit()

    def successful_probe(*_args, **_kwargs) -> BackupSyncConfigTestRead:
        return BackupSyncConfigTestRead(
            ok=True,
            summary="备份机可连接且可写",
            latency_ms=4,
            remote_path_preview="/srv/serino-backups",
            recovery_key_ready=True,
            recovery_key_acknowledged=True,
            remote_history_state="current",
            remote_history_summary="当前站点备份历史正常",
        )

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_machine_connection", successful_probe)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_write_access", successful_probe)

    result = check_backup()

    assert result.status == "warning"
    assert result.summary_key == "diagnostics.result.backupRetrying"
    assert result.action_target == "backup_runs"


def test_backup_diagnostic_fails_when_retries_are_exhausted(seeded_session, monkeypatch) -> None:
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.remote_host = "backup.example.com"
    config.remote_port = 22
    config.remote_path = "/srv/serino-backups"
    config.remote_username = "serino-backup"
    config.credential_ref = "default"
    config.interval_minutes = 60
    config.last_synced_at = utcnow()
    config.last_error = "backup retries exhausted"
    seeded_session.add(
        BackupQueueItem(
            transport="sftp",
            trigger_kind="scheduled",
            status="failed",
            retry_count=4,
            next_retry_at=None,
            last_error="backup retries exhausted",
        )
    )
    seeded_session.commit()

    def successful_probe(*_args, **_kwargs) -> BackupSyncConfigTestRead:
        return BackupSyncConfigTestRead(
            ok=True,
            summary="备份机可连接且可写",
            latency_ms=4,
            remote_path_preview="/srv/serino-backups",
            recovery_key_ready=True,
            recovery_key_acknowledged=True,
            remote_history_state="current",
            remote_history_summary="当前站点备份历史正常",
        )

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_machine_connection", successful_probe)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_write_access", successful_probe)

    result = check_backup()

    assert result.status == "failed"
    assert result.summary_key == "diagnostics.result.backupTaskFailed"
    assert result.action_target == "backup_runs"


def test_backup_diagnostic_rechecks_write_access_when_success_is_stale(seeded_session, monkeypatch) -> None:
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.remote_host = "backup.example.com"
    config.remote_port = 22
    config.remote_path = "/srv/serino-backups"
    config.remote_username = "serino-backup"
    config.credential_ref = "default"
    config.interval_minutes = 60
    config.last_synced_at = utcnow() - timedelta(hours=4)
    config.last_error = None
    seeded_session.commit()
    calls = {"write": 0}

    def successful_probe(*_args, **_kwargs) -> BackupSyncConfigTestRead:
        return BackupSyncConfigTestRead(
            ok=True,
            summary="备份机可连接且可写",
            latency_ms=4,
            remote_path_preview="/srv/serino-backups",
            recovery_key_ready=True,
            recovery_key_acknowledged=True,
            remote_history_state="current",
            remote_history_summary="当前站点备份历史正常",
        )

    def write_probe(*_args, **_kwargs) -> BackupSyncConfigTestRead:
        calls["write"] += 1
        return successful_probe()

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_machine_connection", successful_probe)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_write_access", write_probe)

    result = check_backup()

    assert calls["write"] == 1
    assert result.status == "warning"
    assert result.action_target == "backup_runs"


def test_mcp_diagnostic_requires_an_enabled_connect_key(seeded_session) -> None:
    _set_feature_flags(seeded_session, mcp_public_access=True)
    seeded_session.query(ApiKey).delete()
    seeded_session.commit()

    missing = check_mcp()
    assert missing.status == "failed"
    assert missing.action_target == "mcp"

    seeded_session.add(
        ApiKey(
            key_name="diagnostic-mcp",
            key_prefix="diag-prefix",
            key_suffix="suffix",
            hashed_secret="not-a-real-secret",
            enabled=True,
            scopes=[AGENT_CONNECT, CONTENT_READ],
            mcp_config={},
        )
    )
    seeded_session.commit()

    ready = check_mcp()
    assert ready.status == "healthy"


def test_state_read_overlays_a_new_backup_retry_without_running_external_checks(
    seeded_session,
    monkeypatch,
) -> None:
    checked_at = utcnow() - timedelta(minutes=5)
    _persist_completed_diagnostic_snapshot(
        seeded_session,
        SystemDiagnosticItemRead(
            key="backup",
            status="healthy",
            summary="备份正常",
            summary_key="diagnostics.result.backupHealthy",
            action_target="backup_settings",
            checked_at=checked_at,
        ),
        completed_at=checked_at,
    )
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.last_synced_at = checked_at
    config.last_error = "temporary backup failure"
    seeded_session.add(
        BackupQueueItem(
            transport="sftp",
            trigger_kind="scheduled",
            status="retrying",
            retry_count=1,
            next_retry_at=utcnow() + timedelta(minutes=1),
            last_error="temporary backup failure",
        )
    )
    seeded_session.commit()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("reading a saved diagnostic must not run external checks")

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_machine_connection", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.probe_backup_write_access", forbidden)
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.BitifulObjectStorageProvider", forbidden)

    detailed = get_system_diagnostic_state(include_items=True)
    summary = get_system_diagnostic_state(include_items=False)

    assert detailed.completed_at == checked_at
    assert detailed.overall_status == "attention"
    assert detailed.warning_count == 1
    assert detailed.failed_count == 0
    assert detailed.items[0].status == "warning"
    assert detailed.items[0].summary_key == "diagnostics.result.backupRetrying"
    assert summary.overall_status == "attention"
    assert summary.warning_count == 1
    assert summary.items == []


def test_state_read_clears_a_backup_failure_after_a_newer_success(seeded_session) -> None:
    checked_at = utcnow() - timedelta(minutes=5)
    completed_at = utcnow()
    _persist_completed_diagnostic_snapshot(
        seeded_session,
        SystemDiagnosticItemRead(
            key="backup",
            status="failed",
            summary="备份失败",
            summary_key="diagnostics.result.backupTaskFailed",
            action_target="backup_runs",
            checked_at=checked_at,
        ),
        completed_at=checked_at,
    )
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.last_synced_at = completed_at
    config.last_error = None
    seeded_session.add(
        BackupQueueItem(
            transport="sftp",
            trigger_kind="manual",
            status="completed",
            retry_count=1,
            next_retry_at=None,
            finished_at=completed_at,
            created_at=completed_at,
            updated_at=completed_at,
        )
    )
    seeded_session.commit()

    state = get_system_diagnostic_state(include_items=True)

    assert state.completed_at == checked_at
    assert state.overall_status == "healthy"
    assert state.healthy_count == 1
    assert state.failed_count == 0
    assert state.items[0].status == "healthy"
    assert state.items[0].summary_key == "diagnostics.result.backupHealthy"


def test_state_read_clears_an_object_storage_task_failure_after_a_newer_success(
    seeded_session,
) -> None:
    checked_at = utcnow() - timedelta(minutes=5)
    completed_at = utcnow()
    _persist_completed_diagnostic_snapshot(
        seeded_session,
        SystemDiagnosticItemRead(
            key="object_storage",
            status="failed",
            summary="对象存储同步失败",
            summary_key="diagnostics.result.objectStorageSyncFailures",
            summary_params={"count": 1},
            action_target="object_storage_sync",
            checked_at=checked_at,
        ),
        completed_at=checked_at,
    )
    config = get_or_create_object_storage_config(seeded_session)
    config.enabled = True
    asset = Asset(
        file_name="recovered.webp",
        resource_key="assets/recovered.webp",
        visibility="internal",
        scope="user",
        category="general",
        storage_path="/tmp/recovered.webp",
        storage_provider="bitiful",
        remote_status="available",
        mirror_status="completed",
    )
    seeded_session.add(asset)
    seeded_session.flush()
    seeded_session.add(
        AssetMirrorQueueItem(
            asset_id=asset.id,
            object_key="assets/recovered.webp",
            status="completed",
            retry_count=1,
            next_retry_at=completed_at,
            finished_at=completed_at,
            created_at=completed_at,
            updated_at=completed_at,
        )
    )
    seeded_session.commit()

    state = get_system_diagnostic_state(include_items=True)

    assert state.completed_at == checked_at
    assert state.overall_status == "healthy"
    assert state.healthy_count == 1
    assert state.failed_count == 0
    assert state.items[0].status == "healthy"
    assert state.items[0].summary_key == "diagnostics.result.objectStorageHealthy"


def test_operational_retry_does_not_downgrade_an_object_storage_probe_failure(
    seeded_session,
) -> None:
    checked_at = utcnow() - timedelta(minutes=5)
    _persist_completed_diagnostic_snapshot(
        seeded_session,
        SystemDiagnosticItemRead(
            key="object_storage",
            status="failed",
            summary="对象存储 Bucket 无法访问",
            summary_key="diagnostics.result.objectStorageUnavailable",
            action_target="object_storage",
            checked_at=checked_at,
        ),
        completed_at=checked_at,
    )
    config = get_or_create_object_storage_config(seeded_session)
    config.enabled = True
    asset = Asset(
        file_name="retrying-after-probe-failure.webp",
        resource_key="assets/retrying-after-probe-failure.webp",
        visibility="internal",
        scope="user",
        category="general",
        storage_path="/tmp/retrying-after-probe-failure.webp",
        storage_provider="bitiful",
        remote_status="available",
        mirror_status="retrying",
    )
    seeded_session.add(asset)
    seeded_session.flush()
    seeded_session.add(
        AssetMirrorQueueItem(
            asset_id=asset.id,
            object_key="assets/retrying-after-probe-failure.webp",
            status="retrying",
            retry_count=1,
            next_retry_at=utcnow() + timedelta(minutes=1),
            last_error="temporary upload failure",
        )
    )
    seeded_session.commit()

    state = get_system_diagnostic_state(include_items=True)

    assert state.overall_status == "attention"
    assert state.failed_count == 1
    assert state.warning_count == 0
    assert state.items[0].status == "failed"
    assert state.items[0].summary_key == "diagnostics.result.objectStorageUnavailable"
    assert state.items[0].action_target == "object_storage"


def test_operational_retry_does_not_downgrade_a_backup_probe_failure(seeded_session) -> None:
    checked_at = utcnow() - timedelta(minutes=5)
    _persist_completed_diagnostic_snapshot(
        seeded_session,
        SystemDiagnosticItemRead(
            key="backup",
            status="failed",
            summary="备份机无法连接",
            summary_key="diagnostics.result.backupUnavailable",
            action_target="backup_settings",
            checked_at=checked_at,
        ),
        completed_at=checked_at,
    )
    config = get_or_create_backup_sync_config(seeded_session)
    config.enabled = True
    config.paused = False
    config.last_error = "temporary backup failure"
    seeded_session.add(
        BackupQueueItem(
            transport="sftp",
            trigger_kind="scheduled",
            status="retrying",
            retry_count=1,
            next_retry_at=utcnow() + timedelta(minutes=1),
            last_error="temporary backup failure",
        )
    )
    seeded_session.commit()

    state = get_system_diagnostic_state(include_items=True)

    assert state.overall_status == "attention"
    assert state.failed_count == 1
    assert state.warning_count == 0
    assert state.items[0].status == "failed"
    assert state.items[0].summary_key == "diagnostics.result.backupUnavailable"
    assert state.items[0].action_target == "backup_settings"


def test_runner_persists_the_completed_summary_without_holding_the_claim_session(
    seeded_session,
    monkeypatch,
) -> None:
    queued_state, queued = queue_system_diagnostic_run(trigger_kind="manual")
    assert queued is True
    assert queued_state.execution_status == "queued"

    summary = aggregate_diagnostic_items(
        [
            SystemDiagnosticItemRead(
                key="database",
                status="healthy",
                summary="数据库正常",
                action_target="system",
            ),
            SystemDiagnosticItemRead(
                key="smtp",
                status="skipped",
                summary="未启用",
                action_target="smtp",
            ),
        ]
    )
    monkeypatch.setattr("aerisun.domain.ops.diagnostics.collect_system_diagnostics", lambda: summary)

    assert execute_system_diagnostic_run(queued_state.run_id) is True

    completed = get_system_diagnostic_state()
    assert completed.execution_status == "completed"
    assert completed.overall_status == "healthy"
    assert completed.healthy_count == 1
    assert completed.skipped_count == 1
    assert [item.key for item in completed.items] == ["database", "smtp"]


def test_runner_persists_a_safe_failure_result_when_collection_aborts(
    seeded_session,
    monkeypatch,
    caplog,
) -> None:
    queued_state, queued = queue_system_diagnostic_run(trigger_kind="manual")
    assert queued is True

    def abort_collection():
        raise RuntimeError("unexpected api_key=runner-super-secret")

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.collect_system_diagnostics", abort_collection)

    assert execute_system_diagnostic_run(queued_state.run_id) is False

    completed = get_system_diagnostic_state()
    assert completed.execution_status == "completed"
    assert completed.overall_status == "attention"
    assert completed.failed_count == 1
    assert completed.issue_count == 1
    assert [item.key for item in completed.items] == ["diagnostic_runner"]
    assert "runner-super-secret" not in str(completed.model_dump())
    assert "runner-super-secret" not in caplog.text


def test_state_marks_an_old_completed_result_as_stale(seeded_session, monkeypatch) -> None:
    from aerisun.domain.ops import diagnostics as diagnostics_module

    queued_state, queued = queue_system_diagnostic_run(trigger_kind="manual")
    assert queued is True
    summary = aggregate_diagnostic_items(
        [
            SystemDiagnosticItemRead(
                key="database",
                status="healthy",
                summary="数据库正常",
                action_target="system",
            )
        ]
    )
    monkeypatch.setattr(diagnostics_module, "collect_system_diagnostics", lambda: summary)
    assert execute_system_diagnostic_run(queued_state.run_id) is True

    state_row = seeded_session.get(SystemDiagnosticState, "current")
    assert state_row is not None
    state_row.completed_at = utcnow() - timedelta(hours=37)
    seeded_session.commit()

    stale = get_system_diagnostic_state()
    assert stale.is_stale is True
    assert stale.overall_status == "attention"
    assert stale.issue_count == 1


def test_state_exposes_an_abandoned_run_as_a_failed_runner_item(
    seeded_session,
    monkeypatch,
) -> None:
    from aerisun.domain.ops import diagnostics as diagnostics_module

    queued_state, queued = queue_system_diagnostic_run(trigger_kind="manual")
    assert queued is True
    summary = aggregate_diagnostic_items(
        [
            SystemDiagnosticItemRead(
                key="database",
                status="healthy",
                summary="数据库正常",
                action_target="system",
            )
        ]
    )
    monkeypatch.setattr(diagnostics_module, "collect_system_diagnostics", lambda: summary)
    assert execute_system_diagnostic_run(queued_state.run_id) is True

    _active, active_queued = queue_system_diagnostic_run(trigger_kind="manual")
    assert active_queued is True
    state_row = seeded_session.get(SystemDiagnosticState, "current")
    assert state_row is not None
    state_row.started_at = utcnow() - timedelta(minutes=11)
    seeded_session.commit()

    abandoned = get_system_diagnostic_state()

    assert abandoned.is_running is False
    assert abandoned.overall_status == "attention"
    assert abandoned.failed_count == 1
    assert abandoned.items[0].key == "diagnostic_runner"
    assert abandoned.items[0].status == "failed"
    assert any(item.key == "database" for item in abandoned.items)


def test_startup_diagnostic_skips_a_fresh_completed_result(
    seeded_session,
    monkeypatch,
) -> None:
    from aerisun.domain.ops import diagnostics as diagnostics_module

    queued_state, queued = queue_system_diagnostic_run(trigger_kind="manual")
    assert queued is True
    summary = aggregate_diagnostic_items(
        [
            SystemDiagnosticItemRead(
                key="database",
                status="healthy",
                summary="数据库正常",
                action_target="system",
            )
        ]
    )
    monkeypatch.setattr(diagnostics_module, "collect_system_diagnostics", lambda: summary)
    assert execute_system_diagnostic_run(queued_state.run_id) is True
    monkeypatch.setattr(
        diagnostics_module,
        "run_system_diagnostics",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("fresh results must be reused")),
    )

    state = run_system_diagnostics_if_stale()

    assert state.execution_status == "completed"
    assert state.overall_status == "healthy"


def test_daily_scheduled_diagnostic_runs_only_once_per_boundary(
    seeded_session,
    monkeypatch,
) -> None:
    calls = 0

    def collect_once():
        nonlocal calls
        calls += 1
        return aggregate_diagnostic_items(
            [
                SystemDiagnosticItemRead(
                    key="database",
                    status="healthy",
                    summary="数据库正常",
                    action_target="system",
                )
            ]
        )

    monkeypatch.setattr("aerisun.domain.ops.diagnostics.collect_system_diagnostics", collect_once)

    first = run_scheduled_system_diagnostics()
    second = run_scheduled_system_diagnostics()

    assert first.overall_status == "healthy"
    assert second.run_id == first.run_id
    assert calls == 1
