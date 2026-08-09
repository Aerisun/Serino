from __future__ import annotations

from types import SimpleNamespace

from aerisun.core.settings import get_settings

OBJECT_STORAGE_BASE = "/api/v1/admin/object-storage/config"
SYSTEM_BASE = "/api/v1/admin/system"


def test_object_storage_diagnostic_provider_uses_short_timeouts_and_one_attempt(monkeypatch) -> None:
    import boto3

    from aerisun.domain.media.object_storage import BitifulObjectStorageProvider

    captured: dict[str, object] = {}

    class FakeClient:
        def head_bucket(self, *, Bucket: str) -> None:
            captured["bucket"] = Bucket

    def fake_client(service_name: str, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return FakeClient()

    monkeypatch.setattr(boto3, "client", fake_client)
    config = SimpleNamespace(
        endpoint="https://s3.bitiful.example",
        bucket="asset-bucket",
        region="cn-east-1",
        access_key="access-key",
        secret_key="secret-key",
    )

    provider = BitifulObjectStorageProvider(
        config,
        connect_timeout_seconds=3,
        read_timeout_seconds=5,
        max_attempts=1,
    )
    result = provider.is_healthy()

    boto_config = captured["config"]
    assert boto_config.connect_timeout == 3
    assert boto_config.read_timeout == 5
    assert boto_config.retries["total_max_attempts"] == 1
    assert captured["bucket"] == "asset-bucket"
    assert result.ok is True


def _list_revisions(client, admin_headers, *, resource_key: str) -> list[dict[str, object]]:
    response = client.get(
        f"{SYSTEM_BASE}/config-revisions",
        headers=admin_headers,
        params={"resource_key": resource_key},
    )
    assert response.status_code == 200
    return response.json()["items"]


def _get_revision_detail(client, admin_headers, revision_id: str) -> dict[str, object]:
    response = client.get(f"{SYSTEM_BASE}/config-revisions/{revision_id}", headers=admin_headers)
    assert response.status_code == 200
    return response.json()


def test_object_storage_config_get_returns_default_shape(client, admin_headers):
    response = client.get(OBJECT_STORAGE_BASE, headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["provider"] == "bitiful"
    assert payload["bucket"] == ""
    assert payload["secret_key_configured"] is False
    assert payload["cdn_token_key_configured"] is False
    assert payload["mirror_retry_count"] == 3


def test_object_storage_config_put_persists_and_creates_masked_revision(client, admin_headers, monkeypatch):
    from aerisun.domain.media import object_storage as object_storage_module

    class _Provider:
        def is_healthy(self):
            return object_storage_module.ObjectStorageHealthRead(
                ok=True,
                summary="OSS health ok",
                details={"bucket": "asset-bucket"},
            )

    monkeypatch.setattr(object_storage_module, "build_object_storage_provider", lambda session: _Provider())
    response = client.put(
        OBJECT_STORAGE_BASE,
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "bitiful",
            "bucket": "asset-bucket",
            "endpoint": "https://s3.bitiful.example",
            "region": "cn-east-1",
            "public_base_url": "https://media.example.com",
            "access_key": "ak-test",
            "secret_key": "secret-value",
            "cdn_token_key": "cdn-secret-value",
            "health_check_enabled": False,
            "upload_expire_seconds": 180,
            "public_download_expire_seconds": 420,
            "mirror_bandwidth_limit_bps": 1048576,
            "mirror_retry_count": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["bucket"] == "asset-bucket"
    assert payload["secret_key_configured"] is True
    assert payload["cdn_token_key_configured"] is True
    assert payload["last_health_ok"] is True
    assert isinstance(payload["remote_sync_enqueued_count"], int)
    assert "secret_key" not in payload
    assert "cdn_token_key" not in payload

    current = client.get(OBJECT_STORAGE_BASE, headers=admin_headers)
    assert current.status_code == 200
    current_payload = current.json()
    assert current_payload["bucket"] == "asset-bucket"
    assert current_payload["secret_key_configured"] is True
    assert current_payload["cdn_token_key_configured"] is True
    assert current_payload["last_health_ok"] is True

    revisions = _list_revisions(client, admin_headers, resource_key="integrations.object_storage")
    assert revisions
    detail = _get_revision_detail(client, admin_headers, str(revisions[0]["id"]))
    assert detail["after_preview"]["bucket"] == "asset-bucket"
    assert detail["after_preview"]["secret_key"] == ""
    assert detail["after_preview"]["cdn_token_key"] == ""


def test_object_storage_config_put_is_rejected_while_asset_cleanup_is_pending(
    client,
    admin_headers,
) -> None:
    state_dir = get_settings().data_dir / ".data-migrations"
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest = state_dir / "pending-storage-cleanup.json"
    manifest.write_text("{}", encoding="utf-8")

    response = client.put(
        OBJECT_STORAGE_BASE,
        headers=admin_headers,
        json={"bucket": "must-not-be-saved"},
    )

    assert response.status_code == 409
    assert "稍后再修改 OSS 配置" in response.json()["detail"]


def test_object_storage_config_test_endpoint_uses_transient_payload(client, admin_headers, monkeypatch):
    from aerisun.domain.media import object_storage as object_storage_module

    class _Provider:
        def is_healthy(self):
            return object_storage_module.ObjectStorageHealthRead(
                ok=True,
                summary="OSS config looks healthy",
                details={"bucket": "transient-bucket"},
            )

    monkeypatch.setattr(object_storage_module, "build_object_storage_provider", lambda session: _Provider())

    response = client.post(
        f"{OBJECT_STORAGE_BASE}/test",
        headers=admin_headers,
        json={
            "bucket": "transient-bucket",
            "endpoint": "https://s3.bitiful.example",
            "access_key": "ak-test",
            "secret_key": "secret-value",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["summary"] == "OSS config looks healthy"

    current = client.get(OBJECT_STORAGE_BASE, headers=admin_headers)
    assert current.status_code == 200
    current_payload = current.json()
    assert current_payload["enabled"] is False
    assert current_payload["bucket"] == ""
    assert current_payload["secret_key_configured"] is False


def test_object_storage_config_revision_restore_keeps_secret_flags(client, admin_headers, monkeypatch):
    from aerisun.domain.media import object_storage as object_storage_module

    class _Provider:
        def is_healthy(self):
            return object_storage_module.ObjectStorageHealthRead(
                ok=True,
                summary="OSS health ok",
                details={},
            )

    monkeypatch.setattr(object_storage_module, "build_object_storage_provider", lambda session: _Provider())
    first = client.put(
        OBJECT_STORAGE_BASE,
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "bitiful",
            "bucket": "bucket-one",
            "endpoint": "https://s3.bitiful.example",
            "access_key": "ak-test",
            "secret_key": "secret-one",
            "cdn_token_key": "token-one",
        },
    )
    assert first.status_code == 200

    second = client.put(
        OBJECT_STORAGE_BASE,
        headers=admin_headers,
        json={"bucket": "bucket-two", "public_base_url": "https://media.example.com"},
    )
    assert second.status_code == 200

    latest = _list_revisions(client, admin_headers, resource_key="integrations.object_storage")[0]
    restore = client.post(
        f"{SYSTEM_BASE}/config-revisions/{latest['id']}/restore",
        headers=admin_headers,
        json={"target": "before", "reason": "restore object storage config"},
    )
    assert restore.status_code == 200

    restored = client.get(OBJECT_STORAGE_BASE, headers=admin_headers)
    assert restored.status_code == 200
    payload = restored.json()
    assert payload["bucket"] == "bucket-one"
    assert payload["secret_key_configured"] is True
    assert payload["cdn_token_key_configured"] is True


def test_object_storage_config_put_marks_invalid_when_health_check_fails(client, admin_headers, monkeypatch):
    from aerisun.domain.media import object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "build_object_storage_provider", lambda session: None)

    response = client.put(
        OBJECT_STORAGE_BASE,
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "bitiful",
            "bucket": "broken-bucket",
            "endpoint": "https://broken.example.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["last_health_ok"] is False
    assert "无效" in (payload["last_health_error"] or "") or "不可用" in (payload["last_health_error"] or "")


def test_object_storage_config_put_tests_successfully_even_when_disabled(client, admin_headers, monkeypatch):
    from aerisun.domain.media import object_storage as object_storage_module

    class _Provider:
        def is_healthy(self):
            return object_storage_module.ObjectStorageHealthRead(
                ok=True,
                summary="OSS health ok",
                details={"bucket": "asset-bucket"},
            )

    monkeypatch.setattr(object_storage_module, "build_object_storage_provider", lambda session: _Provider())

    response = client.put(
        OBJECT_STORAGE_BASE,
        headers=admin_headers,
        json={
            "enabled": False,
            "provider": "bitiful",
            "bucket": "asset-bucket",
            "endpoint": "https://s3.bitiful.net",
            "region": "cn-east-1",
            "access_key": "ak-test",
            "secret_key": "secret-value",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["last_health_ok"] is True
    assert payload["last_health_error"] is None
    assert payload["remote_sync_enqueued_count"] == 0


def test_object_storage_config_put_enqueues_local_only_assets_when_enabled(
    client,
    admin_headers,
    monkeypatch,
    seeded_session,
):
    from aerisun.domain.media import object_storage as object_storage_module
    from aerisun.domain.media.models import Asset, AssetRemoteUploadQueueItem

    asset_id = "backfill-asset"
    local_file = get_settings().media_dir / f"assets/user/{asset_id}.png"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"backfill-bytes")

    seeded_session.add(
        Asset(
            id=asset_id,
            file_name="backfill.png",
            resource_key=f"assets/{asset_id}.png",
            visibility="internal",
            scope="user",
            category="general",
            storage_path=str(local_file),
            storage_provider="local",
            remote_status="none",
            mirror_status="completed",
        )
    )
    seeded_session.commit()

    class _Provider:
        def is_healthy(self):
            return object_storage_module.ObjectStorageHealthRead(
                ok=True,
                summary="OSS health ok",
                details={},
            )

    monkeypatch.setattr(object_storage_module, "build_object_storage_provider", lambda session: _Provider())

    response = client.put(
        OBJECT_STORAGE_BASE,
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "bitiful",
            "bucket": "asset-bucket",
            "endpoint": "https://s3.bitiful.net",
            "region": "cn-east-1",
            "access_key": "ak-test",
            "secret_key": "secret-value",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["last_health_ok"] is True
    assert payload["remote_sync_scanned_count"] >= 1
    assert payload["remote_sync_enqueued_count"] >= 1

    queued = seeded_session.query(AssetRemoteUploadQueueItem).all()
    expected_key = f"assets/user/{asset_id}.png"
    assert any(item.object_key == expected_key for item in queued)
    target = next(item for item in queued if item.object_key == expected_key)
    assert target.status == "queued"


def test_object_storage_sync_records_endpoint_returns_mirror_and_delete_records(client, admin_headers, seeded_session):
    from aerisun.domain.media.models import (
        Asset,
        AssetMirrorQueueItem,
        AssetRemoteDeleteQueueItem,
        AssetRemoteUploadQueueItem,
    )

    asset = Asset(
        file_name="test.png",
        resource_key="internal/assets/test/test.png",
        visibility="internal",
        scope="user",
        category="test",
        storage_path="/tmp/test.png",
        storage_provider="bitiful",
        remote_object_key="internal/assets/test/test.png",
        remote_status="available",
        mirror_status="queued",
    )
    seeded_session.add(asset)
    seeded_session.flush()
    seeded_session.add(
        AssetMirrorQueueItem(
            asset_id=asset.id,
            object_key=asset.resource_key,
            status="queued",
            retry_count=1,
        )
    )
    seeded_session.add(
        AssetRemoteDeleteQueueItem(
            object_key="public/assets/old/cleanup.png",
            status="retrying",
            retry_count=2,
            last_error="delete failed",
        )
    )
    seeded_session.add(
        AssetRemoteUploadQueueItem(
            asset_id=asset.id,
            object_key=asset.resource_key,
            status="queued",
            retry_count=0,
        )
    )
    seeded_session.commit()

    response = client.get("/api/v1/admin/object-storage/sync-records", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    record_types = {item["record_type"] for item in payload["items"]}
    assert "mirror" in record_types
    assert "remote_delete" in record_types
    assert "remote_upload" in record_types


def test_failed_object_storage_sync_records_can_be_queued_for_retry(
    client,
    admin_headers,
    seeded_session,
) -> None:
    from aerisun.domain.media.models import (
        Asset,
        AssetLocalDeleteQueueItem,
        AssetMirrorQueueItem,
        AssetRemoteDeleteQueueItem,
        AssetRemoteUploadQueueItem,
    )

    asset = Asset(
        file_name="retry.png",
        resource_key="internal/assets/retry.png",
        visibility="internal",
        scope="user",
        category="test",
        storage_path="/tmp/retry.png",
        storage_provider="bitiful",
        remote_object_key="internal/assets/retry.png",
        remote_status="failed",
        mirror_status="failed",
    )
    seeded_session.add(asset)
    seeded_session.flush()
    records = [
        (
            "mirror",
            AssetMirrorQueueItem(
                asset_id=asset.id,
                object_key=asset.resource_key,
                status="failed",
                retry_count=4,
                last_error="mirror failed",
            ),
        ),
        (
            "local_delete",
            AssetLocalDeleteQueueItem(
                storage_path="/tmp/obsolete.png",
                status="failed",
                retry_count=3,
                last_error="local delete failed",
            ),
        ),
        (
            "remote_delete",
            AssetRemoteDeleteQueueItem(
                object_key="internal/assets/obsolete.png",
                status="failed",
                retry_count=2,
                last_error="remote delete failed",
            ),
        ),
        (
            "remote_upload",
            AssetRemoteUploadQueueItem(
                asset_id=asset.id,
                object_key=asset.resource_key,
                status="failed",
                retry_count=1,
                last_error="upload failed",
            ),
        ),
    ]
    seeded_session.add_all([record for _, record in records])
    seeded_session.commit()

    for record_type, record in records:
        response = client.post(
            f"/api/v1/admin/object-storage/sync-records/{record_type}/{record.id}/retry",
            headers=admin_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == record.id
        assert payload["record_type"] == record_type
        assert payload["status"] == "retrying"
        assert payload["retry_count"] == record.retry_count
        assert payload["last_error"] is None
        seeded_session.expire_all()
        persisted = seeded_session.get(type(record), record.id)
        assert persisted is not None
        assert persisted.status == "retrying"
        assert persisted.last_error is None

    seeded_session.expire_all()
    persisted_asset = seeded_session.get(Asset, asset.id)
    assert persisted_asset is not None
    assert persisted_asset.mirror_status == "retrying"
    assert persisted_asset.remote_status == "retrying"


def test_object_storage_sync_retry_rejects_missing_invalid_and_non_failed_records(
    client,
    admin_headers,
    seeded_session,
) -> None:
    from aerisun.domain.media.models import AssetRemoteDeleteQueueItem

    completed = AssetRemoteDeleteQueueItem(
        object_key="internal/assets/completed.png",
        status="completed",
        retry_count=0,
    )
    seeded_session.add(completed)
    seeded_session.commit()

    conflict = client.post(
        f"/api/v1/admin/object-storage/sync-records/remote_delete/{completed.id}/retry",
        headers=admin_headers,
    )
    missing = client.post(
        "/api/v1/admin/object-storage/sync-records/remote_delete/missing/retry",
        headers=admin_headers,
    )
    invalid = client.post(
        f"/api/v1/admin/object-storage/sync-records/unknown/{completed.id}/retry",
        headers=admin_headers,
    )
    unauthorized = client.post(
        f"/api/v1/admin/object-storage/sync-records/remote_delete/{completed.id}/retry",
    )

    assert conflict.status_code == 409
    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert unauthorized.status_code == 401
