from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from aerisun.core.base import utcnow
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.media import object_storage as media_object_storage
from aerisun.domain.media import repository as media_repo
from aerisun.domain.media.models import (
    Asset,
    AssetMirrorQueueItem,
    AssetRemoteDeleteQueueItem,
    AssetRemoteUploadQueueItem,
)

BASE = "/api/v1/admin/assets"


def test_upload_asset_returns_resource_contract(client, admin_headers):
    response = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("avatar.png", b"avatar-bytes", "image/png")},
        data={"visibility": "internal", "category": "avatar"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["file_name"] == "avatar.png"
    assert payload["visibility"] == "internal"
    assert payload["scope"] == "user"
    assert payload["category"] == "avatar"
    assert payload["resource_key"].startswith("internal/assets/avatar/")
    assert payload["internal_url"] == f"/media/{payload['resource_key']}"
    assert payload["public_url"] is None
    assert Path(payload["storage_path"]).is_file()


def test_upload_public_asset_returns_public_url(client, admin_headers):
    response = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("cover.webp", b"cover-bytes", "image/webp")},
        data={"visibility": "public", "category": "site"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["visibility"] == "public"
    assert payload["scope"] == "user"
    assert payload["resource_key"].startswith("public/assets/site/")
    assert payload["internal_url"] == f"/media/{payload['resource_key']}"
    assert payload["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/{payload['resource_key']}"


def test_update_asset_visibility_returns_absolute_public_url(client, admin_headers):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("headphoto.jpg", b"headphoto-bytes", "image/jpeg")},
        data={"visibility": "internal", "category": "comment"},
    )
    assert created.status_code == 201

    asset = created.json()
    response = client.patch(
        f"{BASE}/{asset['id']}",
        headers=admin_headers,
        json={"visibility": "public"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["visibility"] == "public"
    assert payload["resource_key"].startswith("public/assets/comment/")
    assert payload["internal_url"] == f"/media/{payload['resource_key']}"
    assert payload["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/{payload['resource_key']}"


def test_list_assets_returns_resource_urls(client, admin_headers):
    client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("resume.jpg", b"resume-bytes", "image/jpeg")},
        data={"visibility": "internal", "category": "resume"},
    )

    response = client.get(f"{BASE}/", headers=admin_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["resource_key"].startswith("internal/assets/resume/")
    assert items[0]["scope"] == "user"
    assert items[0]["internal_url"] == f"/media/{items[0]['resource_key']}"


def test_init_upload_returns_local_mode_when_oss_disabled(client, admin_headers):
    response = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "avatar.png",
            "byte_size": 12,
            "sha256": "a" * 64,
            "mime_type": "image/png",
            "visibility": "internal",
            "scope": "user",
            "category": "avatar",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local"
    assert payload["upload_url"] is None
    assert payload["asset"] is None


def test_upload_asset_with_oss_queues_async_mirror_without_writing_local_file(client, admin_headers, monkeypatch):
    from aerisun.domain.media import service as media_service

    class _Provider:
        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            return media_object_storage.ObjectHead(
                content_length=len(data),
                content_type=content_type,
                etag="etag-direct-upload",
                last_modified=utcnow(),
            )

    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: _Provider())
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: _Provider())

    response = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("avatar.png", b"avatar-bytes", "image/png")},
        data={"visibility": "internal", "category": "avatar"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert not Path(payload["storage_path"]).exists()

    with get_session_factory()() as session:
        asset = session.query(Asset).filter_by(id=payload["id"]).one()
        mirrors = session.query(AssetMirrorQueueItem).filter_by(asset_id=payload["id"]).all()
        assert asset.remote_status == "available"
        assert asset.mirror_status == "queued"
        assert len(mirrors) == 1
        assert mirrors[0].status == "queued"
        assert mirrors[0].object_key == payload["resource_key"]


def test_complete_upload_queues_async_mirror_without_writing_local_file(monkeypatch, client, admin_headers):
    from aerisun.domain.media import service as media_service

    class _Provider:
        def sign_upload(self, *, object_key: str, content_type: str | None, expires_in: int) -> str:
            return f"https://upload.example.com/{object_key}"

        def head_object(self, *, object_key: str):
            return media_object_storage.ObjectHead(
                content_length=12,
                content_type="image/png",
                etag="etag-complete-upload",
                last_modified=utcnow(),
            )

    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: _Provider())
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: _Provider())

    plan = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "avatar.png",
            "byte_size": 12,
            "sha256": "a" * 64,
            "mime_type": "image/png",
            "visibility": "internal",
            "scope": "user",
            "category": "avatar",
        },
    )
    assert plan.status_code == 200
    payload = plan.json()
    assert payload["mode"] == "oss"

    complete = client.post(
        f"{BASE}/complete-upload",
        headers=admin_headers,
        json={"asset_id": payload["asset_id"]},
    )
    assert complete.status_code == 200
    complete_payload = complete.json()
    assert not Path(complete_payload["storage_path"]).exists()

    with get_session_factory()() as session:
        asset = session.query(Asset).filter_by(id=payload["asset_id"]).one()
        mirrors = session.query(AssetMirrorQueueItem).filter_by(asset_id=payload["asset_id"]).all()
        assert asset.remote_status == "available"
        assert asset.mirror_status == "queued"
        assert len(mirrors) == 1
        assert mirrors[0].status == "queued"
        assert mirrors[0].object_key == payload["resource_key"]


def test_media_gateway_redirects_when_runtime_remote_link_available(client, admin_headers, monkeypatch):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("cover.webp", b"cover-bytes", "image/webp")},
        data={"visibility": "public", "category": "site"},
    )
    assert created.status_code == 201
    asset = created.json()

    from aerisun.domain.media import service as media_service

    monkeypatch.setattr(
        media_service,
        "sign_asset_download_url",
        lambda session, stored_asset: f"https://cdn.example.com/{stored_asset.resource_key}",
    )

    response = client.get(asset["internal_url"], follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == f"https://cdn.example.com/{asset['resource_key']}"


def test_media_gateway_falls_back_to_local_file_when_oss_redirect_unavailable(client, admin_headers):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("resume.jpg", b"resume-bytes", "image/jpeg")},
        data={"visibility": "internal", "category": "resume"},
    )
    assert created.status_code == 201
    asset = created.json()

    response = client.get(asset["internal_url"])
    assert response.status_code == 200
    assert response.content == b"resume-bytes"


def test_delete_asset_queues_remote_delete_compensation_on_failure(client, admin_headers, monkeypatch):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("cover.webp", b"cover-bytes", "image/webp")},
        data={"visibility": "public", "category": "site"},
    )
    assert created.status_code == 201
    asset = created.json()

    class _Provider:
        def delete_object(self, *, object_key: str) -> None:
            raise RuntimeError(f"delete failed for {object_key}")

    factory = get_session_factory()
    with factory() as session:
        stored = session.query(Asset).filter_by(id=asset["id"]).first()
        assert stored is not None
        stored.storage_provider = "bitiful"
        stored.remote_object_key = stored.resource_key
        stored.remote_status = "available"
        session.commit()

    from aerisun.domain.media import service as media_service

    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: _Provider())
    response = client.delete(f"{BASE}/{asset['id']}", headers=admin_headers)

    assert response.status_code == 204
    with factory() as session:
        assert session.query(Asset).filter_by(id=asset["id"]).first() is None
        queued = session.query(AssetRemoteDeleteQueueItem).all()
        assert len(queued) == 1
        assert queued[0].object_key == asset["resource_key"]
        assert queued[0].status == "queued"
        assert "删除失败" in (queued[0].last_error or "")


def test_delete_asset_records_remote_delete_on_success(client, admin_headers, monkeypatch):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("cover.webp", b"cover-bytes", "image/webp")},
        data={"visibility": "public", "category": "site"},
    )
    assert created.status_code == 201
    asset = created.json()

    deleted_keys: list[str] = []

    class _Provider:
        def delete_object(self, *, object_key: str) -> None:
            deleted_keys.append(object_key)

    factory = get_session_factory()
    with factory() as session:
        stored = session.query(Asset).filter_by(id=asset["id"]).first()
        assert stored is not None
        stored.storage_provider = "bitiful"
        stored.remote_object_key = stored.resource_key
        stored.remote_status = "available"
        session.commit()

    from aerisun.domain.media import service as media_service

    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: _Provider())
    response = client.delete(f"{BASE}/{asset['id']}", headers=admin_headers)

    assert response.status_code == 204
    with factory() as session:
        records = session.query(AssetRemoteDeleteQueueItem).all()
        assert len(records) == 1
        assert records[0].object_key == asset["resource_key"]
        assert records[0].status == "completed"
        assert records[0].last_error is None
    assert deleted_keys == [asset["resource_key"]]


def test_bulk_delete_assets_queues_remote_delete_compensation_on_failure(client, admin_headers, monkeypatch):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("cover.webp", b"cover-bytes", "image/webp")},
        data={"visibility": "public", "category": "site"},
    )
    assert created.status_code == 201
    asset = created.json()

    class _Provider:
        def delete_object(self, *, object_key: str) -> None:
            raise RuntimeError(f"delete failed for {object_key}")

    factory = get_session_factory()
    with factory() as session:
        stored = session.query(Asset).filter_by(id=asset["id"]).first()
        assert stored is not None
        stored.storage_provider = "bitiful"
        stored.remote_object_key = stored.resource_key
        stored.remote_status = "available"
        session.commit()

    from aerisun.domain.media import service as media_service

    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: _Provider())
    response = client.post(
        f"{BASE}/bulk-delete",
        headers=admin_headers,
        json={"ids": [asset["id"]]},
    )

    assert response.status_code == 200
    assert response.json()["affected"] == 1
    with factory() as session:
        assert session.query(Asset).filter_by(id=asset["id"]).first() is None
        queued = session.query(AssetRemoteDeleteQueueItem).all()
        assert len(queued) == 1
        assert queued[0].object_key == asset["resource_key"]
        assert queued[0].status == "queued"


def test_remote_delete_compensation_dispatcher_retries_then_completes(monkeypatch, seeded_session):
    queued = media_object_storage.queue_remote_asset_delete(
        seeded_session,
        object_key="public/assets/site/test.webp",
        error="initial failure",
    )
    seeded_session.commit()
    queue_item_id = queued.id

    class _FailingProvider:
        def delete_object(self, *, object_key: str) -> None:
            raise RuntimeError(f"delete boom: {object_key}")

    monkeypatch.setattr(
        media_object_storage,
        "build_object_storage_maintenance_provider",
        lambda session: _FailingProvider(),
    )
    media_object_storage.dispatch_due_remote_asset_delete_jobs()

    factory = get_session_factory()
    with factory() as session:
        failed_item = media_repo.get_remote_delete_queue_item(session, queue_item_id)
        assert failed_item is not None
        assert failed_item.status == "retrying"
        assert failed_item.retry_count == 1
        assert "delete boom" in (failed_item.last_error or "")
        failed_item.next_retry_at = utcnow() - timedelta(seconds=1)
        session.commit()

    deleted_keys: list[str] = []

    class _SuccessfulProvider:
        def delete_object(self, *, object_key: str) -> None:
            deleted_keys.append(object_key)

    monkeypatch.setattr(
        media_object_storage,
        "build_object_storage_maintenance_provider",
        lambda session: _SuccessfulProvider(),
    )
    media_object_storage.dispatch_due_remote_asset_delete_jobs()

    with factory() as session:
        completed_item = media_repo.get_remote_delete_queue_item(session, queue_item_id)
        assert completed_item is not None
        assert completed_item.status == "completed"
        assert completed_item.retry_count == 1
        assert completed_item.last_error is None
    assert deleted_keys == ["public/assets/site/test.webp"]


def test_remote_upload_reconcile_and_dispatcher_sync_local_asset(monkeypatch, seeded_session, tmp_path):
    local_file = tmp_path / "media" / "public" / "assets" / "site" / "sync.png"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"sync-bytes")

    asset = Asset(
        file_name="sync.png",
        resource_key="public/assets/site/sync.png",
        visibility="public",
        scope="user",
        category="site",
        storage_path=str(local_file),
        mime_type="image/png",
        storage_provider="local",
        remote_status="none",
        mirror_status="completed",
    )
    seeded_session.add(asset)
    seeded_session.commit()

    uploaded: list[tuple[str, bytes, str | None]] = []

    class _Provider:
        def is_healthy(self):
            return media_object_storage.ObjectStorageHealthRead(ok=True, summary="ok", details={})

        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            uploaded.append((object_key, data, content_type))
            return media_object_storage.ObjectHead(
                content_length=len(data),
                content_type=content_type,
                etag="etag-sync",
                last_modified=utcnow(),
            )

    monkeypatch.setattr(
        media_object_storage,
        "build_object_storage_maintenance_provider",
        lambda session: _Provider(),
    )

    enqueued = media_object_storage.reconcile_object_storage_remote_sync()
    assert enqueued == 0

    with get_session_factory()() as session:
        config = media_object_storage.get_or_create_object_storage_config(session)
        config.enabled = True
        session.commit()

    enqueued = media_object_storage.reconcile_object_storage_remote_sync()
    assert enqueued >= 1

    with get_session_factory()() as session:
        queued = session.query(AssetRemoteUploadQueueItem).all()
        assert any(item.object_key == "public/assets/site/sync.png" for item in queued)
        target = next(item for item in queued if item.object_key == "public/assets/site/sync.png")
        assert target.status == "queued"
        for item in queued:
            if item.object_key != "public/assets/site/sync.png":
                item.next_retry_at = utcnow() + timedelta(hours=1)
        session.commit()

    media_object_storage.dispatch_due_remote_asset_upload_jobs()

    with get_session_factory()() as session:
        updated = session.query(Asset).filter_by(id=asset.id).first()
        queued = session.query(AssetRemoteUploadQueueItem).filter_by(object_key="public/assets/site/sync.png").all()
        assert updated is not None
        assert updated.remote_status == "available"
        assert updated.storage_provider == "bitiful"
        assert updated.remote_etag == "etag-sync"
        assert len(queued) == 1
        assert queued[0].status == "completed"

    assert uploaded == [("public/assets/site/sync.png", b"sync-bytes", "image/png")]
