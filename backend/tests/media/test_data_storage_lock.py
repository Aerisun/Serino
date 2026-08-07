from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Event, Thread

import pytest

from aerisun.core.data_storage_lock import exclusive_data_storage_lock
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.exceptions import StateConflict
from aerisun.domain.media import object_storage as object_storage_service
from aerisun.domain.media import service as media_service
from aerisun.domain.media.models import Asset, AssetRemoteUploadQueueItem
from aerisun.domain.media.object_storage import ObjectHead
from aerisun.domain.media.schemas import AssetAdminUpdate, ObjectStorageConfigUpdate
from aerisun.domain.ops import backup_sync


class _ScopeMoveProvider:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)

    def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None) -> ObjectHead:
        self.objects[object_key] = self.objects[source_key]
        return ObjectHead(
            content_length=len(self.objects[object_key]),
            content_type=content_type,
            etag="copy",
            last_modified=None,
        )

    def download_to_local(self, *, object_key: str, dest_path: Path, bandwidth_limit_bps: int | None):
        content = self.objects[object_key]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content)
        return len(content), "download"

    def delete_object(self, *, object_key: str) -> None:
        self.objects.pop(object_key, None)


def _create_locked_test_asset(
    session, *, asset_id: str, content: bytes, remote: bool
) -> tuple[Asset, Path, str | None]:
    path = get_settings().media_dir / f"assets/user/{asset_id}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    remote_key = f"assets/user/{asset_id}.png" if remote else None
    asset = Asset(
        id=asset_id,
        file_name="locked.png",
        resource_key=f"assets/{asset_id}.png",
        visibility="internal",
        scope="user",
        category="general",
        storage_path=str(path),
        mime_type="image/png",
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_provider="bitiful" if remote else "local",
        remote_object_key=remote_key,
        remote_status="available" if remote else "none",
        mirror_status="completed",
    )
    session.add(asset)
    session.commit()
    return asset, path, remote_key


def test_scope_move_waits_for_migration_storage_lock_and_keeps_local_and_remote_targets(
    seeded_session,
    monkeypatch,
) -> None:
    content = b"scope-move-lock"
    asset, old_path, old_remote = _create_locked_test_asset(
        seeded_session,
        asset_id="scope-move-lock",
        content=content,
        remote=True,
    )
    assert old_remote is not None
    provider = _ScopeMoveProvider({old_remote: content})
    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda _session: provider)
    started = Event()
    finished = Event()
    errors: list[BaseException] = []

    def move_scope() -> None:
        started.set()
        try:
            with get_session_factory()() as session:
                media_service.update_asset(session, asset.id, AssetAdminUpdate(scope="visitor"))
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            finished.set()

    with exclusive_data_storage_lock():
        worker = Thread(target=move_scope)
        worker.start()
        assert started.wait(timeout=1)
        assert not finished.wait(timeout=0.2)

    worker.join(timeout=5)
    assert not worker.is_alive()
    assert errors == []
    seeded_session.expire_all()
    moved = seeded_session.get(Asset, asset.id)
    assert moved is not None
    new_path = get_settings().media_dir / f"assets/visitor/{asset.id}.png"
    new_remote = f"assets/visitor/{asset.id}.png"
    assert moved.scope == "visitor"
    assert Path(moved.storage_path) == new_path
    assert new_path.read_bytes() == content
    assert not old_path.exists()
    assert moved.remote_object_key == new_remote
    assert provider.objects == {new_remote: content}


def test_asset_delete_waits_for_migration_storage_lock(seeded_session) -> None:
    asset, path, _remote = _create_locked_test_asset(
        seeded_session,
        asset_id="delete-lock",
        content=b"delete-lock",
        remote=False,
    )
    asset_id = asset.id
    started = Event()
    finished = Event()
    errors: list[BaseException] = []

    def delete() -> None:
        started.set()
        try:
            with get_session_factory()() as session:
                media_service.delete_asset(session, asset_id)
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            finished.set()

    with exclusive_data_storage_lock():
        worker = Thread(target=delete)
        worker.start()
        assert started.wait(timeout=1)
        assert not finished.wait(timeout=0.2)

    worker.join(timeout=5)
    assert not worker.is_alive()
    assert errors == []
    seeded_session.expire_all()
    assert seeded_session.get(Asset, asset_id) is None
    assert not path.exists()


def test_pending_cleanup_rejects_scope_move_and_delete_until_manifest_is_removed(seeded_session) -> None:
    move_asset, move_path, _move_remote = _create_locked_test_asset(
        seeded_session,
        asset_id="pending-cleanup-move",
        content=b"pending-cleanup-move",
        remote=False,
    )
    delete_asset, delete_path, _delete_remote = _create_locked_test_asset(
        seeded_session,
        asset_id="pending-cleanup-delete",
        content=b"pending-cleanup-delete",
        remote=False,
    )
    state_dir = get_settings().data_dir / ".data-migrations"
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest = state_dir / "pending-storage-cleanup.json"
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(StateConflict, match="稍后再修改资源范围"):
        media_service.update_asset(
            seeded_session,
            move_asset.id,
            AssetAdminUpdate(scope="visitor"),
        )
    with pytest.raises(StateConflict, match="稍后再删除资源"):
        media_service.delete_asset(seeded_session, delete_asset.id)

    assert move_path.read_bytes() == b"pending-cleanup-move"
    assert delete_path.read_bytes() == b"pending-cleanup-delete"
    assert seeded_session.get(Asset, move_asset.id) is not None
    assert seeded_session.get(Asset, delete_asset.id) is not None

    manifest.unlink()
    state_dir.rmdir()
    moved = media_service.update_asset(
        seeded_session,
        move_asset.id,
        AssetAdminUpdate(scope="visitor"),
    )
    media_service.delete_asset(seeded_session, delete_asset.id)

    assert moved.scope == "visitor"
    assert Path(moved.storage_path).read_bytes() == b"pending-cleanup-move"
    assert not move_path.exists()
    assert seeded_session.get(Asset, delete_asset.id) is None
    assert not delete_path.exists()


def test_pending_cleanup_rejects_object_storage_config_changes(seeded_session) -> None:
    config = object_storage_service.get_or_create_object_storage_config(seeded_session)
    original_bucket = config.bucket
    original_queue_count = seeded_session.query(AssetRemoteUploadQueueItem).count()
    state_dir = get_settings().data_dir / ".data-migrations"
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest = state_dir / "pending-storage-cleanup.json"
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(StateConflict, match="稍后再修改 OSS 配置"):
        object_storage_service.update_object_storage_config(
            seeded_session,
            ObjectStorageConfigUpdate(bucket="new-bucket"),
        )

    seeded_session.expire_all()
    assert object_storage_service.get_or_create_object_storage_config(seeded_session).bucket == original_bucket
    assert seeded_session.query(AssetRemoteUploadQueueItem).count() == original_queue_count

    manifest.unlink()
    state_dir.rmdir()
    updated = object_storage_service.update_object_storage_config(
        seeded_session,
        ObjectStorageConfigUpdate(bucket="new-bucket"),
    )
    assert updated.bucket == "new-bucket"


def test_pending_cleanup_skips_backup_dispatch_and_rejects_manual_backup_operations(
    seeded_session,
    monkeypatch,
) -> None:
    state_dir = get_settings().data_dir / ".data-migrations"
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest = state_dir / "pending-storage-cleanup.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        backup_sync,
        "get_session_factory",
        lambda: (_ for _ in ()).throw(AssertionError("pending dispatch must not open the database")),
    )

    assert backup_sync.dispatch_backup_sync() is None
    with pytest.raises(StateConflict, match="稍后再创建备份"):
        backup_sync.trigger_backup_sync(seeded_session)
    with pytest.raises(StateConflict, match="稍后再重试备份"):
        backup_sync.retry_backup_sync_run(seeded_session, "missing")
    with pytest.raises(StateConflict, match="稍后再恢复备份"):
        backup_sync.restore_backup_commit(seeded_session, "missing")
    with pytest.raises(StateConflict, match="稍后再恢复备份"):
        backup_sync.restore_backup_snapshot(seeded_session, "missing")
    with pytest.raises(StateConflict, match="稍后再恢复备份"):
        backup_sync.restore_remote_backup_history(seeded_session, object())  # type: ignore[arg-type]
