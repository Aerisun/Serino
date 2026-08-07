from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest
from sqlalchemy import text

from aerisun.core.data_migrations.runner import (
    apply_pending_data_migrations,
    cleanup_applied_data_migrations,
    collect_migration_status,
    rollback_external_data_migrations,
)
from aerisun.core.data_migrations.state import get_migration_entry
from aerisun.core.db import get_session_factory, run_database_migrations
from aerisun.core.production_baseline import apply_production_baseline
from aerisun.core.settings import get_settings
from aerisun.domain.content.models import DiaryEntry, PostEntry
from aerisun.domain.media.models import (
    Asset,
    AssetLocalDeleteQueueItem,
    AssetMirrorQueueItem,
    AssetRemoteDeleteQueueItem,
    AssetRemoteUploadQueueItem,
)
from aerisun.domain.media.object_storage import ObjectHead, ObjectStorageEntry
from aerisun.domain.site_config.models import PageCopy
from aerisun.domain.waline.service import connect_waline_db
from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

asset_storage_layout_v1 = importlib.import_module(
    "aerisun.core.data_migrations.versions.0019_asset_storage_layout_backfill"
)


class FakeObjectStorage:
    def __init__(
        self,
        objects: dict[str, bytes],
        *,
        fail_copy: bool = False,
        fail_delete_once: str | None = None,
    ) -> None:
        self.objects = dict(objects)
        self.fail_copy = fail_copy
        self.fail_delete_once = fail_delete_once
        self.copied: list[tuple[str, str]] = []
        self.uploaded: list[tuple[str, str | None]] = []
        self.deleted: list[str] = []

    def list_objects(self, *, prefix: str) -> tuple[ObjectStorageEntry, ...]:
        return tuple(
            ObjectStorageEntry(object_key=key, content_length=len(value), etag=f"etag-{len(value)}")
            for key, value in sorted(self.objects.items())
            if key.startswith(prefix)
        )

    def head_object(self, *, object_key: str) -> ObjectHead:
        content = self.objects[object_key]
        return ObjectHead(
            content_length=len(content), content_type=None, etag=f"etag-{len(content)}", last_modified=None
        )

    def find_object(self, *, object_key: str) -> ObjectHead | None:
        if object_key not in self.objects:
            return None
        return self.head_object(object_key=object_key)

    def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None) -> ObjectHead:
        if self.fail_copy:
            raise RuntimeError("copy failed")
        self.objects[object_key] = self.objects[source_key]
        self.copied.append((source_key, object_key))
        return self.head_object(object_key=object_key)

    def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None) -> ObjectHead:
        self.objects[object_key] = data
        return self.head_object(object_key=object_key)

    def upload_local_file(self, *, object_key: str, source_path: Path, content_type: str | None) -> ObjectHead:
        self.objects[object_key] = source_path.read_bytes()
        self.uploaded.append((object_key, content_type))
        return self.head_object(object_key=object_key)

    def download_to_local(self, *, object_key: str, dest_path: Path, bandwidth_limit_bps: int | None):
        content = self.objects[object_key]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content)
        return len(content), f"etag-{len(content)}"

    def delete_object(self, *, object_key: str) -> None:
        if self.fail_delete_once == object_key:
            self.fail_delete_once = None
            raise RuntimeError("delete failed")
        self.objects.pop(object_key, None)
        self.deleted.append(object_key)


@pytest.fixture()
def migration_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    run_database_migrations()
    factory = get_session_factory()
    with factory() as session:
        yield session
    teardown_runtime_state()


def _seed_shared_legacy_asset(session, *, content: bytes = b"legacy-image") -> tuple[Asset, str, Path]:
    media_root = get_settings().media_dir.expanduser().resolve()
    old_key = "internal/assets/markdown-image/shared.png"
    old_url = f"/media/{old_key}"
    old_path = media_root / old_key
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(content)
    asset = Asset(
        id="asset-shared",
        file_name="shared.png",
        resource_key=old_key,
        public_slug="shared-public.png",
        visibility="internal",
        scope="user",
        category="markdown-image",
        storage_path=str(old_path),
        mime_type="image/png",
        byte_size=len(content),
        storage_provider="bitiful",
        remote_object_key=old_key,
        remote_status="available",
        mirror_status="completed",
    )
    session.add_all(
        (
            asset,
            PostEntry(slug="migration-post", title="Post", body=f"![post]({old_url})", tags=[], visibility="public"),
            DiaryEntry(
                slug="migration-diary",
                title="Diary",
                body=f'<img src="{old_url}?diary=1">',
                tags=[],
                visibility="public",
            ),
        )
    )
    session.commit()
    with connect_waline_db(get_settings().waline_db_path) as connection:
        connection.execute(
            "INSERT INTO wl_comment (comment, url) VALUES (?, ?)",
            (f'<img src="{old_url}">', "/guestbook"),
        )
    return asset, old_url, old_path


def test_asset_storage_backfill_migrates_all_references_and_leaves_exact_storage_sets(migration_session) -> None:
    asset, old_url, old_path = _seed_shared_legacy_asset(migration_session)
    provider = FakeObjectStorage(
        {
            asset.remote_object_key: b"legacy-image",
            "assets/article/": b"",
        }
    )

    report = asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    migration_session.refresh(asset)
    canonical_url = f"/media/assets/{asset.id}.png"
    new_local_path = get_settings().media_dir / f"assets/article/{asset.id}.png"
    new_remote_key = f"assets/article/{asset.id}.png"
    assert asset.scope == "article"
    assert asset.category == "post"
    assert asset.resource_key == f"assets/{asset.id}.png"
    assert asset.public_slug is None
    assert Path(asset.storage_path) == new_local_path
    assert asset.remote_object_key == new_remote_key
    assert new_local_path.read_bytes() == b"legacy-image"
    assert not old_path.exists()
    assert not (get_settings().media_dir / "internal").exists()
    assert {entry.object_key for entry in provider.list_objects(prefix="assets/")} == {new_remote_key}
    assert provider.objects[new_remote_key] == b"legacy-image"

    post = migration_session.query(PostEntry).filter_by(slug="migration-post").one()
    diary = migration_session.query(DiaryEntry).filter_by(slug="migration-diary").one()
    assert post.body == f"![post]({canonical_url})"
    assert diary.body == f'<img src="{canonical_url}?diary=1">'
    with connect_waline_db(get_settings().waline_db_path) as connection:
        comment = connection.execute("SELECT comment FROM wl_comment").fetchone()
    assert comment is not None
    assert comment["comment"] == f'<img src="{canonical_url}">'
    assert old_url not in post.body
    assert report.migrated_asset_count == 1
    assert report.rewritten_reference_count == 3
    assert report.local_actual_keys == report.local_expected_keys
    assert report.remote_actual_keys == report.remote_expected_keys

    second = asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    assert second.migrated_asset_count == 0
    assert second.rewritten_reference_count == 0
    assert {entry.object_key for entry in provider.list_objects(prefix="assets/")} == {new_remote_key}


def test_asset_storage_backfill_prefers_each_exact_legacy_path_when_identical_files_have_two_records(
    migration_session,
) -> None:
    content = b"same-hero-content"
    media_root = get_settings().media_dir.expanduser().resolve()
    assets: list[Asset] = []
    for visibility in ("internal", "public"):
        asset_id = f"duplicate-{visibility}-hero"
        resource_key = f"{visibility}/assets/hero-image/shared.webp"
        path = media_root / resource_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        assets.append(
            Asset(
                id=asset_id,
                file_name="shared.webp",
                resource_key=resource_key,
                visibility=visibility,
                scope="system",
                category="hero-image",
                storage_path=str(path),
                mime_type="image/webp",
                byte_size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                storage_provider="local",
                remote_status="none",
                mirror_status="completed",
            )
        )
    post = PostEntry(
        slug="duplicate-legacy-paths",
        title="Duplicate legacy paths",
        body=(
            "![internal](/media/internal/assets/hero-image/shared.webp)\n"
            "![public](/media/public/assets/hero-image/shared.webp)"
        ),
        tags=[],
        visibility="public",
    )
    migration_session.add_all([*assets, post])
    migration_session.commit()
    provider = FakeObjectStorage({})

    asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    migration_session.refresh(post)
    assert post.body == (
        f"![internal](/media/assets/{assets[0].id}.webp)\n![public](/media/assets/{assets[1].id}.webp)"
    )
    assert all((media_root / f"assets/article/{asset.id}.webp").read_bytes() == content for asset in assets)
    assert not (media_root / "internal").exists()
    assert not (media_root / "public").exists()


def test_asset_storage_backfill_preflight_rejects_unhandled_reference_before_copying(migration_session) -> None:
    asset, old_url, old_path = _seed_shared_legacy_asset(migration_session)
    migration_session.execute(text("CREATE TABLE unknown_content (id TEXT PRIMARY KEY, body TEXT NOT NULL)"))
    migration_session.execute(
        text("INSERT INTO unknown_content (id, body) VALUES ('unknown', :body)"),
        {"body": old_url},
    )
    migration_session.commit()
    provider = FakeObjectStorage({asset.remote_object_key: b"legacy-image"})

    with pytest.raises(RuntimeError, match=r"unknown_content\.body"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    assert old_path.exists()
    assert provider.copied == []
    migration_session.refresh(asset)
    assert asset.resource_key.startswith("internal/assets/")


def test_asset_storage_backfill_copy_failure_removes_prepared_targets_and_keeps_old_state(migration_session) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    provider = FakeObjectStorage({asset.remote_object_key: b"legacy-image"}, fail_copy=True)

    with pytest.raises(RuntimeError, match="copy failed"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    target_local = get_settings().media_dir / f"assets/article/{asset.id}.png"
    target_remote = f"assets/article/{asset.id}.png"
    assert old_path.exists()
    assert not target_local.exists()
    assert target_remote not in provider.objects
    migration_session.refresh(asset)
    assert asset.resource_key.startswith("internal/assets/")
    assert asset.remote_object_key.startswith("internal/assets/")


def test_asset_storage_backfill_does_not_treat_head_failure_as_a_missing_target(migration_session) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    target_remote = f"assets/article/{asset.id}.png"

    class HeadFailureProvider(FakeObjectStorage):
        def __init__(self) -> None:
            super().__init__(
                {
                    str(asset.remote_object_key): b"legacy-image",
                    target_remote: b"pre-existing-unrelated-content",
                }
            )
            self.failed = False

        def head_object(self, *, object_key: str) -> ObjectHead:
            if object_key == target_remote and not self.failed:
                self.failed = True
                raise RuntimeError("temporary head failure")
            return super().head_object(object_key=object_key)

    provider = HeadFailureProvider()

    with pytest.raises(RuntimeError, match="temporary head failure"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    migration_session.refresh(asset)
    assert asset.resource_key.startswith("internal/assets/")
    assert old_path.read_bytes() == b"legacy-image"
    assert provider.objects[target_remote] == b"pre-existing-unrelated-content"
    assert provider.copied == []


def test_asset_storage_backfill_stops_when_registered_oss_assets_cannot_be_inspected(migration_session) -> None:
    asset, old_url, old_path = _seed_shared_legacy_asset(migration_session)

    with pytest.raises(RuntimeError, match="OSS 当前不可用"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=None,
        )

    migration_session.refresh(asset)
    assert asset.resource_key.startswith("internal/assets/")
    assert asset.remote_object_key.startswith("internal/assets/")
    assert old_path.read_bytes() == b"legacy-image"
    post = migration_session.query(PostEntry).filter_by(slug="migration-post").one()
    assert old_url in post.body
    assert not asset_storage_layout_v1.migration_manifest_path().exists()


def test_asset_storage_backfill_rejects_untrusted_symlink_without_deleting_it(migration_session) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    provider = FakeObjectStorage({asset.remote_object_key: b"legacy-image"})
    assets_root = get_settings().media_dir / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)
    untrusted_link = assets_root / "unexpected-link"
    untrusted_link.symlink_to(old_path)

    with pytest.raises(RuntimeError, match="符号链接"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    migration_session.refresh(asset)
    assert asset.resource_key.startswith("internal/assets/")
    assert old_path.exists()
    assert untrusted_link.is_symlink()
    assert provider.objects == {asset.remote_object_key: b"legacy-image"}
    assert not asset_storage_layout_v1.migration_manifest_path().exists()


def test_asset_storage_backfill_rejects_unknown_media_root_entry_before_copying(migration_session) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    provider = FakeObjectStorage({asset.remote_object_key: b"legacy-image"})
    unknown = get_settings().media_dir / "unknown-residue.bin"
    unknown.write_bytes(b"do-not-touch")

    with pytest.raises(RuntimeError, match="媒体根目录存在未知条目"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    migration_session.refresh(asset)
    assert asset.resource_key.startswith("internal/assets/")
    assert old_path.exists()
    assert unknown.read_bytes() == b"do-not-touch"
    assert provider.copied == []


def test_asset_storage_backfill_adopts_unregistered_local_file_without_leaving_an_orphan(migration_session) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    old_path = media_root / "public/assets/misc/unregistered.webp"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"unregistered-local-image")
    provider = FakeObjectStorage({})

    report = asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    adopted = migration_session.query(Asset).one()
    expected_local = media_root / f"assets/user/{adopted.id}.webp"
    expected_remote = f"assets/user/{adopted.id}.webp"
    assert adopted.scope == "user"
    assert adopted.category == "general"
    assert adopted.visibility == "public"
    assert adopted.resource_key == f"assets/{adopted.id}.webp"
    assert Path(adopted.storage_path) == expected_local
    assert expected_local.read_bytes() == b"unregistered-local-image"
    assert adopted.remote_object_key == expected_remote
    assert provider.objects == {expected_remote: b"unregistered-local-image"}
    assert not old_path.exists()
    assert not (media_root / "public").exists()
    assert report.local_actual_keys == report.local_expected_keys == frozenset({f"assets/user/{adopted.id}.webp"})
    assert report.remote_actual_keys == report.remote_expected_keys == frozenset({expected_remote})


def test_asset_storage_backfill_adopts_unregistered_remote_file_and_removes_legacy_key(migration_session) -> None:
    old_remote_key = "internal/assets/misc/remote-only.png"
    provider = FakeObjectStorage(
        {
            old_remote_key: b"unregistered-remote-image",
            "internal/assets/": b"",
        }
    )

    report = asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    adopted = migration_session.query(Asset).one()
    expected_local = get_settings().media_dir / f"assets/user/{adopted.id}.png"
    expected_remote = f"assets/user/{adopted.id}.png"
    assert adopted.visibility == "internal"
    assert adopted.scope == "user"
    assert adopted.category == "general"
    assert expected_local.read_bytes() == b"unregistered-remote-image"
    assert provider.objects == {expected_remote: b"unregistered-remote-image"}
    assert old_remote_key not in provider.objects
    assert report.local_actual_keys == report.local_expected_keys
    assert report.remote_actual_keys == report.remote_expected_keys


def test_asset_storage_backfill_honors_active_delete_queues_without_resurrecting_assets(migration_session) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    objects: dict[str, bytes] = {}
    queued_local_paths: list[Path] = []
    queued_remote_keys: list[str] = []
    for index, status in enumerate(("queued", "running", "retrying", "failed"), start=1):
        resource_key = f"internal/assets/deleted/pending-{index}.png"
        local_path = media_root / resource_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(f"deleted-{index}".encode())
        queued_local_paths.append(local_path)
        queued_remote_keys.append(resource_key)
        objects[resource_key] = local_path.read_bytes()
        migration_session.add_all(
            (
                AssetLocalDeleteQueueItem(storage_path=str(local_path), status=status),
                AssetRemoteDeleteQueueItem(object_key=resource_key, status=status),
            )
        )
    migration_session.commit()
    provider = FakeObjectStorage(objects)

    report = asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    assert migration_session.query(Asset).count() == 0
    assert migration_session.query(AssetLocalDeleteQueueItem).count() == 0
    assert migration_session.query(AssetRemoteDeleteQueueItem).count() == 0
    assert not any(path.exists() for path in queued_local_paths)
    assert not any(key in provider.objects for key in queued_remote_keys)
    assert report.local_actual_keys == report.local_expected_keys == frozenset()
    assert report.remote_actual_keys == report.remote_expected_keys == frozenset()


def test_asset_storage_backfill_migrates_registered_remote_only_asset(migration_session) -> None:
    content = b"remote-only-registered"
    old_key = "internal/assets/pending/remote-only.png"
    old_path = get_settings().media_dir / old_key
    asset = Asset(
        id="remote-only-asset",
        file_name="remote-only.png",
        resource_key=old_key,
        visibility="internal",
        scope="user",
        category="general",
        storage_path=str(old_path),
        mime_type="image/png",
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_provider="bitiful",
        remote_object_key=old_key,
        remote_status="available",
        mirror_status="queued",
    )
    migration_session.add(asset)
    migration_session.commit()
    provider = FakeObjectStorage({old_key: content})

    asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    migration_session.refresh(asset)
    expected_local = get_settings().media_dir / f"assets/user/{asset.id}.png"
    expected_remote = f"assets/user/{asset.id}.png"
    assert expected_local.read_bytes() == content
    assert asset.remote_object_key == expected_remote
    assert provider.objects == {expected_remote: content}
    assert not old_path.exists()


def test_asset_storage_backfill_uploads_verified_local_source_when_queued_old_remote_is_missing(
    migration_session,
) -> None:
    content = b"queued-remote-upload"
    old_key = "internal/assets/pending/local-source.png"
    old_path = get_settings().media_dir / old_key
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(content)
    asset = Asset(
        id="queued-upload-asset",
        file_name="local-source.png",
        resource_key=old_key,
        visibility="internal",
        scope="user",
        category="general",
        storage_path=str(old_path),
        mime_type="image/png",
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_provider="bitiful",
        remote_object_key=old_key,
        remote_status="queued",
        mirror_status="completed",
    )
    migration_session.add(asset)
    migration_session.commit()
    provider = FakeObjectStorage({})

    asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    migration_session.refresh(asset)
    expected_remote = f"assets/user/{asset.id}.png"
    assert asset.remote_object_key == expected_remote
    assert provider.objects == {expected_remote: content}
    assert provider.uploaded == [(expected_remote, "image/png")]
    assert old_key not in provider.deleted


def test_fresh_baseline_rewrites_public_slug_without_uploading_when_oss_is_disabled(
    migration_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_production_baseline(force=True)
    provider = FakeObjectStorage({})
    monkeypatch.setattr(
        asset_storage_layout_v1,
        "build_object_storage_maintenance_provider",
        lambda _session: provider,
    )

    asset_storage_layout_v1.apply(migration_session)
    migration_session.commit()
    asset_storage_layout_v1.finalize(migration_session)
    asset_storage_layout_v1.cleanup(migration_session)

    assets = {asset.category: asset for asset in migration_session.query(Asset).all()}
    hero = assets["hero-image"]
    permanent_url = f"/media/assets/{hero.id}{Path(hero.file_name).suffix}"
    friends_page = migration_session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
    markdown = friends_page.extras["applicationMarkdown"]
    assert hero.public_slug is None
    assert "/media/avatar" not in markdown
    assert permanent_url in markdown
    assert all(asset.remote_object_key is None for asset in assets.values())
    assert all(asset.storage_provider == "local" for asset in assets.values())
    assert provider.objects == {}


def test_fresh_baseline_current_only_manifest_recovers_when_database_commit_did_not_happen(
    migration_session,
) -> None:
    apply_production_baseline(force=True)
    provider = FakeObjectStorage({})

    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
        mirror_local_assets_to_oss=False,
    )
    migration_session.rollback()

    hero = migration_session.query(Asset).filter(Asset.category == "hero-image").one()
    assert hero.public_slug == "avatar"
    assert asset_storage_layout_v1.migration_manifest_path().is_file()

    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
        mirror_local_assets_to_oss=False,
    )
    migration_session.commit()
    asset_storage_layout_v1.verify_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    asset_storage_layout_v1.finalize_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )

    migration_session.refresh(hero)
    assert hero.public_slug is None
    assert not asset_storage_layout_v1.migration_manifest_path().exists()


def test_asset_storage_backfill_removes_only_verified_stale_scope_copy(migration_session) -> None:
    content = b"same-canonical-scope-copy"
    asset_id = "stale-scope-copy"
    media_root = get_settings().media_dir.expanduser().resolve()
    current_path = media_root / f"assets/user/{asset_id}.pdf"
    stale_path = media_root / f"assets/visitor/{asset_id}.pdf"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(content)
    stale_path.write_bytes(content)
    asset = Asset(
        id=asset_id,
        file_name="copy.pdf",
        resource_key=f"assets/{asset_id}.pdf",
        visibility="internal",
        scope="user",
        category="general",
        storage_path=str(current_path),
        mime_type="application/pdf",
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_provider="local",
        remote_status="none",
        mirror_status="completed",
    )
    migration_session.add(asset)
    migration_session.commit()

    asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=None,
    )
    migration_session.commit()

    assert current_path.read_bytes() == content
    assert not stale_path.exists()


def test_asset_storage_backfill_rejects_different_stale_scope_copy_without_deleting_it(
    migration_session,
) -> None:
    content = b"registered-content"
    asset_id = "conflicting-scope-copy"
    media_root = get_settings().media_dir.expanduser().resolve()
    current_path = media_root / f"assets/user/{asset_id}.pdf"
    stale_path = media_root / f"assets/visitor/{asset_id}.pdf"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(content)
    stale_path.write_bytes(b"different-content")
    migration_session.add(
        Asset(
            id=asset_id,
            file_name="copy.pdf",
            resource_key=f"assets/{asset_id}.pdf",
            visibility="internal",
            scope="user",
            category="general",
            storage_path=str(current_path),
            mime_type="application/pdf",
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_provider="local",
            remote_status="none",
            mirror_status="completed",
        )
    )
    migration_session.commit()

    with pytest.raises(RuntimeError, match="当前目录残留副本内容不一致"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=None,
        )

    assert current_path.read_bytes() == content
    assert stale_path.read_bytes() == b"different-content"
    assert not asset_storage_layout_v1.migration_manifest_path().exists()


def test_cleanup_rejects_unlisted_stale_local_copy_after_manifest_tamper(migration_session) -> None:
    content = b"manifest-local-stale-copy"
    asset_id = "manifest-local-stale"
    media_root = get_settings().media_dir.expanduser().resolve()
    current_path = media_root / f"assets/user/{asset_id}.pdf"
    stale_path = media_root / f"assets/visitor/{asset_id}.pdf"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(content)
    stale_path.write_bytes(content)
    migration_session.add(
        Asset(
            id=asset_id,
            file_name="copy.pdf",
            resource_key=f"assets/{asset_id}.pdf",
            visibility="internal",
            scope="user",
            category="general",
            storage_path=str(current_path),
            mime_type="application/pdf",
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_provider="local",
            remote_status="none",
            mirror_status="completed",
        )
    )
    migration_session.commit()
    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=None,
    )
    migration_session.commit()
    asset_storage_layout_v1.verify_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=None,
    )
    payload = asset_storage_layout_v1._read_manifest()
    assert payload is not None
    payload["canonical_delete_local_paths"] = []
    asset_storage_layout_v1._write_json_atomic(asset_storage_layout_v1.migration_manifest_path(), payload)

    with pytest.raises(RuntimeError, match="本地资源集合不一致"):
        asset_storage_layout_v1.finalize_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=None,
        )

    assert current_path.read_bytes() == content
    assert stale_path.read_bytes() == content
    assert asset_storage_layout_v1.migration_manifest_path().is_file()


def test_cleanup_rejects_unlisted_stale_remote_copy_after_manifest_tamper(migration_session) -> None:
    content = b"manifest-remote-stale-copy"
    asset_id = "manifest-remote-stale"
    media_root = get_settings().media_dir.expanduser().resolve()
    current_path = media_root / f"assets/user/{asset_id}.pdf"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(content)
    current_remote = f"assets/user/{asset_id}.pdf"
    stale_remote = f"assets/visitor/{asset_id}.pdf"
    migration_session.add(
        Asset(
            id=asset_id,
            file_name="copy.pdf",
            resource_key=f"assets/{asset_id}.pdf",
            visibility="internal",
            scope="user",
            category="general",
            storage_path=str(current_path),
            mime_type="application/pdf",
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_provider="bitiful",
            remote_object_key=current_remote,
            remote_status="available",
            mirror_status="completed",
        )
    )
    migration_session.commit()
    provider = FakeObjectStorage({current_remote: content, stale_remote: content})
    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()
    asset_storage_layout_v1.verify_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    payload = asset_storage_layout_v1._read_manifest()
    assert payload is not None
    payload["canonical_delete_remote_keys"] = []
    asset_storage_layout_v1._write_json_atomic(asset_storage_layout_v1.migration_manifest_path(), payload)

    with pytest.raises(RuntimeError, match="OSS 资源集合不一致"):
        asset_storage_layout_v1.finalize_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    assert provider.objects == {current_remote: content, stale_remote: content}
    assert asset_storage_layout_v1.migration_manifest_path().is_file()


def test_asset_storage_backfill_finalizer_failure_keeps_both_copies_and_resumes_cleanly(migration_session) -> None:
    asset, old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage(
        {old_remote_key: b"legacy-image"},
        fail_delete_once=old_remote_key,
    )

    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()

    migration_session.refresh(asset)
    new_local = Path(asset.storage_path)
    new_remote = str(asset.remote_object_key)
    assert asset.resource_key == f"assets/{asset.id}.png"
    assert new_local.exists()
    assert old_path.exists()
    assert old_remote_key in provider.objects
    assert new_remote in provider.objects
    assert asset_storage_layout_v1.migration_manifest_path().is_file()

    with pytest.raises(RuntimeError, match="delete failed"):
        asset_storage_layout_v1.finalize_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    assert new_local.exists()
    assert new_remote in provider.objects
    assert old_path.exists()
    assert old_remote_key in provider.objects
    assert asset_storage_layout_v1.migration_manifest_path().is_file()

    report = asset_storage_layout_v1.finalize_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    assert not old_path.exists()
    assert old_remote_key not in provider.objects
    assert new_local.exists()
    assert new_remote in provider.objects
    assert not asset_storage_layout_v1.migration_manifest_path().exists()
    assert report.local_actual_keys == report.local_expected_keys
    assert report.remote_actual_keys == report.remote_expected_keys

    post = migration_session.query(PostEntry).filter_by(slug="migration-post").one()
    assert old_url not in post.body


def test_asset_storage_backfill_finalizer_checks_new_copy_before_deleting_old_copy(migration_session) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage({old_remote_key: b"legacy-image"})

    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()
    migration_session.refresh(asset)
    new_remote_key = str(asset.remote_object_key)
    provider.objects[new_remote_key] = b"corrupt-copy"

    with pytest.raises(RuntimeError, match="目标 OSS 对象摘要校验失败"):
        asset_storage_layout_v1.finalize_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    assert old_path.exists()
    assert old_remote_key in provider.objects
    assert provider.objects[old_remote_key] == b"legacy-image"
    assert asset_storage_layout_v1.migration_manifest_path().is_file()


def test_asset_storage_cleanup_fails_before_any_delete_when_oss_becomes_unavailable(migration_session) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage({old_remote_key: b"legacy-image"})
    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()
    asset_storage_layout_v1.verify_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )

    with pytest.raises(RuntimeError, match="OSS 当前不可用"):
        asset_storage_layout_v1.finalize_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=None,
        )

    assert old_path.exists()
    assert old_remote_key in provider.objects


def test_asset_storage_cleanup_rejects_new_legacy_file_without_deleting_known_sources(migration_session) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage({old_remote_key: b"legacy-image"})
    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.commit()
    asset_storage_layout_v1.verify_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    unexpected = get_settings().media_dir / "internal/assets/unexpected-after-prepare.png"
    unexpected.parent.mkdir(parents=True, exist_ok=True)
    unexpected.write_bytes(b"do-not-delete")

    with pytest.raises(RuntimeError, match="本地旧资源集合不一致"):
        asset_storage_layout_v1.finalize_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    assert old_path.exists()
    assert old_remote_key in provider.objects
    assert unexpected.read_bytes() == b"do-not-delete"


def test_asset_storage_retry_removes_only_owned_staging_files_from_state_directory(migration_session) -> None:
    asset, _old_url, _old_path = _seed_shared_legacy_asset(migration_session)
    provider = FakeObjectStorage({str(asset.remote_object_key): b"legacy-image"})
    staging_dir = asset_storage_layout_v1._migration_temp_dir()
    staging_dir.mkdir(parents=True, exist_ok=True)
    stale_staging = staging_dir / "local-copy.interrupted.tmp"
    stale_staging.write_bytes(b"partial")

    asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )

    assert not stale_staging.exists()
    assert not staging_dir.exists()


def test_asset_storage_backfill_restores_waline_snapshot_before_retrying_uncommitted_prepare(
    migration_session,
) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    old_key = "internal/assets/comment-only.png"
    old_url = f"/media/{old_key}"
    old_path = media_root / old_key
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"comment-only-image")
    asset = Asset(
        id="asset-comment-only",
        file_name="comment-only.png",
        resource_key=old_key,
        visibility="internal",
        scope="user",
        category="general",
        storage_path=str(old_path),
        mime_type="image/png",
        byte_size=len(b"comment-only-image"),
        storage_provider="bitiful",
        remote_object_key=old_key,
        remote_status="available",
        mirror_status="completed",
    )
    migration_session.add(asset)
    migration_session.commit()
    with connect_waline_db(get_settings().waline_db_path) as connection:
        connection.execute(
            "INSERT INTO wl_comment (comment, url) VALUES (?, ?)",
            (f'<img src="{old_url}">', "/posts/example"),
        )
    provider = FakeObjectStorage({old_key: b"comment-only-image"})

    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )
    migration_session.rollback()  # 模拟 Waline 已提交、主数据库尚未提交时进程被强杀。

    asset_storage_layout_v1.prepare_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )

    retried_asset = migration_session.get(Asset, asset.id)
    assert retried_asset is not None
    assert retried_asset.scope == "visitor"
    assert retried_asset.category == "comment"


def test_asset_storage_backfill_rewrites_waline_avatar_references(migration_session) -> None:
    asset, old_url, _old_path = _seed_shared_legacy_asset(migration_session)
    with connect_waline_db(get_settings().waline_db_path) as connection:
        connection.execute(
            "UPDATE wl_comment SET avatar = ?, comment = 'avatar only'",
            (old_url,),
        )
    provider = FakeObjectStorage({str(asset.remote_object_key): b"legacy-image"})

    asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )

    with connect_waline_db(get_settings().waline_db_path) as connection:
        avatar = connection.execute("SELECT avatar FROM wl_comment").fetchone()
    assert avatar is not None
    assert avatar["avatar"] == f"/media/assets/{asset.id}.png"


def test_asset_storage_backfill_clears_stale_transfer_queues_after_canonical_copies_are_ready(
    migration_session,
) -> None:
    asset, _old_url, _old_path = _seed_shared_legacy_asset(migration_session)
    old_key = str(asset.remote_object_key)
    migration_session.add_all(
        (
            AssetMirrorQueueItem(asset_id=asset.id, object_key=old_key),
            AssetRemoteUploadQueueItem(asset_id=asset.id, object_key=old_key),
        )
    )
    migration_session.commit()
    provider = FakeObjectStorage({old_key: b"legacy-image"})

    asset_storage_layout_v1.migrate_asset_storage_layout(
        migration_session,
        waline_db_path=get_settings().waline_db_path,
        provider=provider,
    )

    assert migration_session.query(AssetMirrorQueueItem).count() == 0
    assert migration_session.query(AssetRemoteUploadQueueItem).count() == 0


def test_asset_storage_backfill_rejects_old_path_that_overlaps_another_assets_target(migration_session) -> None:
    first, _old_url, first_old_path = _seed_shared_legacy_asset(migration_session)
    second_path = get_settings().media_dir / "assets/user/asset-second.png"
    second_path.parent.mkdir(parents=True, exist_ok=True)
    second_path.write_bytes(b"second-image")
    second = Asset(
        id="asset-second",
        file_name="second.png",
        resource_key="assets/asset-second.png",
        visibility="internal",
        scope="user",
        category="general",
        storage_path=str(second_path),
        mime_type="image/png",
        byte_size=len(b"second-image"),
        storage_provider="bitiful",
        remote_object_key="assets/user/asset-second.png",
        remote_status="available",
        mirror_status="completed",
    )
    migration_session.add(second)
    migration_session.commit()
    first_old_path.unlink()
    first.storage_path = str(second_path)
    first.byte_size = len(b"second-image")
    first.remote_object_key = str(first.resource_key)
    migration_session.commit()
    provider = FakeObjectStorage(
        {
            str(first.remote_object_key): b"second-image",
            str(second.remote_object_key): b"second-image",
        }
    )

    with pytest.raises(RuntimeError, match=r"本地地址.*不可信|目标路径重叠"):
        asset_storage_layout_v1.migrate_asset_storage_layout(
            migration_session,
            waline_db_path=get_settings().waline_db_path,
            provider=provider,
        )

    assert not first_old_path.exists()
    assert second_path.read_bytes() == b"second-image"


def test_official_data_migration_runner_resumes_0019_cleanup_after_interruption(
    migration_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage(
        {old_remote_key: b"legacy-image"},
        fail_delete_once=old_remote_key,
    )
    monkeypatch.setattr(
        asset_storage_layout_v1,
        "build_object_storage_maintenance_provider",
        lambda _session: provider,
    )

    with pytest.raises(RuntimeError, match="delete failed"):
        apply_pending_data_migrations(mode="blocking")

    migration_session.expire_all()
    migrated_asset = migration_session.get(Asset, asset.id)
    assert migrated_asset is not None
    new_local = Path(migrated_asset.storage_path)
    new_remote_key = str(migrated_asset.remote_object_key)
    assert migrated_asset.resource_key == f"assets/{asset.id}.png"
    assert old_path.exists()
    assert new_local.exists()
    assert old_remote_key in provider.objects
    assert new_remote_key in provider.objects
    journal = get_migration_entry(migration_session, asset_storage_layout_v1.migration_key)
    assert journal is not None
    # 破坏性清理在 journal durable applied 之后执行；清理失败不得把已迁移数据库降回 failed。
    assert journal.status == "applied"

    assert apply_pending_data_migrations(mode="blocking") == []
    migration_session.expire_all()
    journal = get_migration_entry(migration_session, asset_storage_layout_v1.migration_key)
    assert journal is not None
    assert journal.status == "applied"
    assert not old_path.exists()
    assert old_remote_key not in provider.objects
    assert new_local.exists()
    assert new_remote_key in provider.objects
    assert not asset_storage_layout_v1.migration_manifest_path().exists()


def test_official_runner_can_defer_destructive_cleanup_until_release_is_healthy(
    migration_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage({old_remote_key: b"legacy-image"})
    monkeypatch.setattr(
        asset_storage_layout_v1,
        "build_object_storage_maintenance_provider",
        lambda _session: provider,
    )

    applied = apply_pending_data_migrations(mode="blocking", defer_cleanup=True)

    assert asset_storage_layout_v1.migration_key in applied
    migration_session.expire_all()
    migrated = migration_session.get(Asset, asset.id)
    assert migrated is not None
    new_remote_key = str(migrated.remote_object_key)
    assert old_path.exists()
    assert old_remote_key in provider.objects
    assert new_remote_key in provider.objects
    assert asset_storage_layout_v1.migration_manifest_path().is_file()
    assert asset_storage_layout_v1.migration_key in collect_migration_status()["blocking"]["cleanup_pending"]

    assert asset_storage_layout_v1.migration_key in cleanup_applied_data_migrations(mode="blocking")
    assert not old_path.exists()
    assert old_remote_key not in provider.objects
    assert new_remote_key in provider.objects
    assert not asset_storage_layout_v1.migration_manifest_path().exists()
    assert asset_storage_layout_v1.migration_key not in collect_migration_status()["blocking"]["cleanup_pending"]


def test_release_rollback_removes_only_remote_targets_owned_by_this_attempt(
    migration_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage({old_remote_key: b"legacy-image"})
    monkeypatch.setattr(
        asset_storage_layout_v1,
        "build_object_storage_maintenance_provider",
        lambda _session: provider,
    )
    apply_pending_data_migrations(mode="blocking", defer_cleanup=True)
    migration_session.expire_all()
    migrated = migration_session.get(Asset, asset.id)
    assert migrated is not None
    new_remote_key = str(migrated.remote_object_key)

    assert asset_storage_layout_v1.migration_key in rollback_external_data_migrations(mode="blocking")

    assert old_path.exists()
    assert old_remote_key in provider.objects
    assert new_remote_key not in provider.objects
    assert asset_storage_layout_v1.migration_manifest_path().is_file()


def test_release_rollback_never_deletes_a_matching_target_that_existed_before_the_attempt(
    migration_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset, _old_url, _old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    target_remote_key = f"assets/article/{asset.id}.png"
    provider = FakeObjectStorage(
        {
            old_remote_key: b"legacy-image",
            target_remote_key: b"legacy-image",
        }
    )
    monkeypatch.setattr(
        asset_storage_layout_v1,
        "build_object_storage_maintenance_provider",
        lambda _session: provider,
    )
    apply_pending_data_migrations(mode="blocking", defer_cleanup=True)

    rollback_external_data_migrations(mode="blocking")

    assert provider.objects[old_remote_key] == b"legacy-image"
    assert provider.objects[target_remote_key] == b"legacy-image"


def test_deferred_cleanup_tolerates_new_canonical_assets_created_after_health_check(
    migration_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset, _old_url, old_path = _seed_shared_legacy_asset(migration_session)
    old_remote_key = str(asset.remote_object_key)
    provider = FakeObjectStorage({old_remote_key: b"legacy-image"})
    monkeypatch.setattr(
        asset_storage_layout_v1,
        "build_object_storage_maintenance_provider",
        lambda _session: provider,
    )
    apply_pending_data_migrations(mode="blocking", defer_cleanup=True)

    new_asset_id = "asset-created-after-ready"
    new_local = get_settings().media_dir / f"assets/user/{new_asset_id}.png"
    new_local.parent.mkdir(parents=True, exist_ok=True)
    new_local.write_bytes(b"new-after-ready")
    new_remote = f"assets/user/{new_asset_id}.png"
    provider.objects[new_remote] = b"new-after-ready"
    migration_session.add(
        Asset(
            id=new_asset_id,
            file_name="new.png",
            resource_key=f"assets/{new_asset_id}.png",
            visibility="internal",
            scope="user",
            category="general",
            storage_path=str(new_local),
            mime_type="image/png",
            byte_size=len(b"new-after-ready"),
            storage_provider="bitiful",
            remote_object_key=new_remote,
            remote_status="available",
            mirror_status="completed",
        )
    )
    migration_session.commit()

    cleanup_applied_data_migrations(mode="blocking")

    assert not old_path.exists()
    assert old_remote_key not in provider.objects
    assert new_local.read_bytes() == b"new-after-ready"
    assert provider.objects[new_remote] == b"new-after-ready"
