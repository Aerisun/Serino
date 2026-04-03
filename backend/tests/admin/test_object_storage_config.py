from __future__ import annotations

OBJECT_STORAGE_BASE = "/api/v1/admin/object-storage/config"
SYSTEM_BASE = "/api/v1/admin/system"


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


def test_object_storage_config_put_persists_and_creates_masked_revision(client, admin_headers):
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
    assert "secret_key" not in payload
    assert "cdn_token_key" not in payload

    current = client.get(OBJECT_STORAGE_BASE, headers=admin_headers)
    assert current.status_code == 200
    current_payload = current.json()
    assert current_payload["bucket"] == "asset-bucket"
    assert current_payload["secret_key_configured"] is True
    assert current_payload["cdn_token_key_configured"] is True

    revisions = _list_revisions(client, admin_headers, resource_key="integrations.object_storage")
    assert revisions
    detail = _get_revision_detail(client, admin_headers, str(revisions[0]["id"]))
    assert detail["after_preview"]["bucket"] == "asset-bucket"
    assert detail["after_preview"]["secret_key"] == ""
    assert detail["after_preview"]["cdn_token_key"] == ""


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


def test_object_storage_config_revision_restore_keeps_secret_flags(client, admin_headers):
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
