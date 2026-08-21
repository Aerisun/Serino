from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from aerisun.core.base import utcnow
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.content.models import PostEntry
from aerisun.domain.iam.models import AdminSession
from aerisun.domain.media import object_storage as media_object_storage
from aerisun.domain.media import repository as media_repo
from aerisun.domain.media.models import (
    Asset,
    AssetLocalDeleteQueueItem,
    AssetMirrorQueueItem,
    AssetRemoteDeleteQueueItem,
    AssetRemoteUploadQueueItem,
)

BASE = "/api/v1/admin/assets"


def test_delete_asset_rejects_live_content_reference(client, admin_headers):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("referenced.png", b"referenced-bytes", "image/png")},
        data={"scope": "article", "category": "post"},
    )
    assert created.status_code == 201
    asset = created.json()

    with get_session_factory()() as session:
        session.add(
            PostEntry(
                slug="asset-delete-reference",
                title="Asset delete reference",
                body=f"![image]({asset['internal_url']})",
                tags=[],
                visibility="public",
            )
        )
        session.commit()

    response = client.delete(f"{BASE}/{asset['id']}", headers=admin_headers)

    assert response.status_code == 409
    assert "posts.body" in response.json()["detail"]
    assert Path(asset["storage_path"]).is_file()
    with get_session_factory()() as session:
        assert session.get(Asset, asset["id"]) is not None


def test_upload_asset_returns_resource_contract(client, admin_headers):
    response = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("avatar.png", b"avatar-bytes", "image/png")},
        data={"visibility": "internal", "scope": "article", "category": "post"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["file_name"] == "avatar.png"
    assert payload["visibility"] == "internal"
    assert payload["scope"] == "article"
    assert payload["category"] == "post"
    assert payload["resource_key"] == f"assets/{payload['id']}.png"
    assert payload["internal_url"] == f"/media/{payload['resource_key']}"
    assert payload["public_url"] is None
    assert Path(payload["storage_path"]) == get_settings().media_dir / f"assets/article/{payload['id']}.png"
    assert Path(payload["storage_path"]).read_bytes() == b"avatar-bytes"


def test_admin_open_url_returns_internal_file_directly_to_browser(client, admin_headers):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("paper.pdf", b"pdf-bytes", "application/pdf")},
        data={"visibility": "internal", "scope": "user", "category": "general"},
    )
    assert created.status_code == 201
    asset = created.json()

    opened = client.post(f"{BASE}/{asset['id']}/open-url", headers=admin_headers)

    assert opened.status_code == 200
    open_url = opened.json()["url"]
    parsed = urlsplit(open_url)
    preview_tokens = parse_qs(parsed.query).get("preview_token")
    assert parsed.path == asset["internal_url"]
    assert preview_tokens and len(preview_tokens[0]) > 40

    response = client.get(
        open_url,
        headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"},
    )
    assert response.status_code == 200
    assert response.content == b"pdf-bytes"
    assert response.headers["content-type"].startswith("application/pdf")

    token = preview_tokens[0]
    version, encoded_payload, signature = token.split(".", maxsplit=2)
    replacement = "a" if encoded_payload[0] != "a" else "b"
    tampered_token = f"{version}.{replacement}{encoded_payload[1:]}.{signature}"
    tampered_url = f"{parsed.path}?preview_token={tampered_token}"
    assert (
        client.get(
            tampered_url,
            headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"{parsed.path}?preview_token=not-a-valid-token",
            headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"},
        ).status_code
        == 403
    )

    with get_session_factory()() as session:
        admin_session = session.query(AdminSession).filter_by(session_token="test-admin-session-token").one()
        session.delete(admin_session)
        session.commit()
    assert (
        client.get(
            open_url,
            headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"},
        ).status_code
        == 403
    )


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
    assert payload["resource_key"] == f"assets/{payload['id']}.webp"
    assert payload["internal_url"] == f"/media/{payload['resource_key']}"
    assert payload["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/{payload['resource_key']}"


def test_upload_public_asset_with_slug_returns_short_url_and_preserves_resource_url(client, admin_headers):
    response = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("cover.webp", b"cover-slug-bytes", "image/webp")},
        data={"visibility": "public", "category": "site", "public_slug": "hero-cover.webp"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["public_slug"] == "hero-cover.webp"
    assert payload["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/hero-cover.webp"

    slug_response = client.get("/media/hero-cover.webp")
    assert slug_response.status_code == 200
    assert slug_response.content == b"cover-slug-bytes"

    original_response = client.get(f"/media/{payload['resource_key']}")
    assert original_response.status_code == 200
    assert original_response.content == b"cover-slug-bytes"


def test_internal_asset_slug_is_retained_but_not_public_until_visibility_changes(client, admin_headers):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("private.webp", b"private-slug-bytes", "image/webp")},
        data={"visibility": "internal", "category": "site", "public_slug": "private-cover.webp"},
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["public_slug"] == "private-cover.webp"
    assert payload["public_url"] is None
    assert client.get("/media/private-cover.webp").status_code == 404

    published = client.patch(
        f"{BASE}/{payload['id']}",
        headers=admin_headers,
        json={"visibility": "public"},
    )

    assert published.status_code == 200
    published_payload = published.json()
    assert published_payload["public_slug"] == "private-cover.webp"
    assert published_payload["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/private-cover.webp"
    slug_response = client.get("/media/private-cover.webp")
    assert slug_response.status_code == 200
    assert slug_response.content == b"private-slug-bytes"


def test_asset_slug_must_be_unique(client, admin_headers):
    first = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("first.webp", b"first-slug-bytes", "image/webp")},
        data={"visibility": "public", "category": "site", "public_slug": "shared-cover.webp"},
    )
    assert first.status_code == 201

    duplicate = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("second.webp", b"second-slug-bytes", "image/webp")},
        data={"visibility": "public", "category": "site", "public_slug": "shared-cover.webp"},
    )

    assert duplicate.status_code == 409
    assert "slug" in duplicate.json()["detail"].lower()


def test_asset_slug_rejects_reserved_and_invalid_values(client, admin_headers):
    invalid_slugs = ["public", "internal", "BadSlug", "bad slug", "bad/slug"]

    for public_slug in invalid_slugs:
        response = client.post(
            f"{BASE}/",
            headers=admin_headers,
            files={"file": (f"{public_slug.replace('/', '-')}.webp", b"bad-slug-bytes", "image/webp")},
            data={"visibility": "public", "category": "site", "public_slug": public_slug},
        )

        assert response.status_code == 422, public_slug


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
    assert payload["resource_key"] == asset["resource_key"]
    assert payload["resource_key"] == f"assets/{payload['id']}.jpg"
    assert payload["internal_url"] == f"/media/{payload['resource_key']}"
    assert payload["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/{payload['resource_key']}"


def test_update_asset_category_is_metadata_only_and_scope_moves_local_file(client, admin_headers):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("note.png", b"note-bytes", "image/png")},
        data={"scope": "user", "category": "general"},
    )
    assert created.status_code == 201
    original = created.json()
    original_path = Path(original["storage_path"])

    categorized = client.patch(
        f"{BASE}/{original['id']}",
        headers=admin_headers,
        json={"category": "custom"},
    )
    assert categorized.status_code == 200
    assert categorized.json()["resource_key"] == original["resource_key"]
    assert categorized.json()["storage_path"] == original["storage_path"]
    assert original_path.read_bytes() == b"note-bytes"

    moved = client.patch(
        f"{BASE}/{original['id']}",
        headers=admin_headers,
        json={"scope": "article"},
    )
    assert moved.status_code == 200
    payload = moved.json()
    next_path = get_settings().media_dir / f"assets/article/{original['id']}.png"
    assert payload["resource_key"] == original["resource_key"]
    assert payload["internal_url"] == original["internal_url"]
    assert Path(payload["storage_path"]) == next_path
    assert next_path.read_bytes() == b"note-bytes"
    assert not original_path.exists()


def test_update_asset_scope_copies_remote_object_before_switching_database(client, admin_headers, monkeypatch):
    from aerisun.domain.media import service as media_service

    copied: list[tuple[str, str]] = []
    deleted: list[str] = []
    objects: dict[str, bytes] = {}

    class _Provider:
        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            objects[object_key] = data
            return media_object_storage.ObjectHead(
                content_length=len(data), content_type=content_type, etag="upload", last_modified=utcnow()
            )

        def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None):
            copied.append((source_key, object_key))
            objects[object_key] = objects[source_key]
            return media_object_storage.ObjectHead(
                content_length=len(b"remote-scope"), content_type=content_type, etag="copy", last_modified=utcnow()
            )

        def download_to_local(self, *, object_key: str, dest_path: Path, bandwidth_limit_bps: int | None):
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(objects[object_key])
            return len(objects[object_key]), "download"

        def delete_object(self, *, object_key: str) -> None:
            deleted.append(object_key)
            objects.pop(object_key, None)

    provider = _Provider()
    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: provider)
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: provider)
    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: provider)

    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("remote.png", b"remote-scope", "image/png")},
        data={"scope": "user", "category": "general"},
    )
    assert created.status_code == 201
    original = created.json()

    moved = client.patch(f"{BASE}/{original['id']}", headers=admin_headers, json={"scope": "visitor"})

    assert moved.status_code == 200
    payload = moved.json()
    old_key = f"assets/user/{original['id']}.png"
    new_key = f"assets/visitor/{original['id']}.png"
    assert payload["resource_key"] == original["resource_key"]
    assert copied == [(old_key, new_key)]
    assert deleted == [old_key]
    with get_session_factory()() as session:
        stored = session.query(Asset).filter_by(id=original["id"]).one()
        assert stored.scope == "visitor"
        assert stored.remote_object_key == new_key


def test_update_asset_scope_copy_failure_keeps_old_paths_and_cleans_target(client, admin_headers, monkeypatch):
    from aerisun.domain.media import service as media_service

    deleted: list[str] = []

    class _Provider:
        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            return media_object_storage.ObjectHead(
                content_length=len(data), content_type=content_type, etag="upload", last_modified=utcnow()
            )

        def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None):
            raise RuntimeError("copy unavailable")

        def delete_object(self, *, object_key: str) -> None:
            deleted.append(object_key)

    provider = _Provider()
    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: provider)
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: provider)
    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: provider)
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: provider)

    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("remote.png", b"remote-failure", "image/png")},
        data={"scope": "user", "category": "general"},
    )
    assert created.status_code == 201
    original = created.json()

    response = client.patch(f"{BASE}/{original['id']}", headers=admin_headers, json={"scope": "article"})

    assert response.status_code == 409
    target_key = f"assets/article/{original['id']}.png"
    assert deleted == [target_key]
    with get_session_factory()() as session:
        stored = session.query(Asset).filter_by(id=original["id"]).one()
        assert stored.scope == "user"
        assert stored.resource_key == original["resource_key"]
        assert stored.remote_object_key == f"assets/user/{original['id']}.png"


def test_update_asset_scope_persists_cleanup_retry_when_target_delete_fails(client, admin_headers, monkeypatch):
    from aerisun.domain.media import service as media_service

    class _Provider:
        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            return media_object_storage.ObjectHead(
                content_length=len(data), content_type=content_type, etag="upload", last_modified=utcnow()
            )

        def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None):
            return media_object_storage.ObjectHead(
                content_length=1, content_type=content_type, etag="wrong-size", last_modified=utcnow()
            )

        def delete_object(self, *, object_key: str) -> None:
            raise RuntimeError("temporary delete failure")

    provider = _Provider()
    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: provider)
    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: provider)
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: provider)

    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("remote.png", b"remote-cleanup-retry", "image/png")},
        data={"scope": "user", "category": "general"},
    )
    assert created.status_code == 201
    asset = created.json()

    response = client.patch(f"{BASE}/{asset['id']}", headers=admin_headers, json={"scope": "article"})

    assert response.status_code == 409
    target_key = f"assets/article/{asset['id']}.png"
    with get_session_factory()() as session:
        stored = session.get(Asset, asset["id"])
        cleanup = session.query(AssetRemoteDeleteQueueItem).filter_by(object_key=target_key).one()
        assert stored is not None
        assert stored.scope == "user"
        assert stored.remote_object_key == f"assets/user/{asset['id']}.png"
        assert cleanup.status == "queued"
        assert "temporary delete failure" in (cleanup.last_error or "")


def test_update_asset_scope_rejects_inconsistent_current_storage_path(client, admin_headers):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("inconsistent.png", b"inconsistent", "image/png")},
        data={"scope": "user", "category": "general"},
    )
    assert created.status_code == 201
    asset = created.json()
    original_path = Path(asset["storage_path"])
    wrong_path = get_settings().media_dir / f"assets/system/{asset['id']}.png"
    wrong_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.replace(wrong_path)
    with get_session_factory()() as session:
        stored = session.get(Asset, asset["id"])
        assert stored is not None
        stored.storage_path = str(wrong_path)
        session.commit()

    response = client.patch(f"{BASE}/{asset['id']}", headers=admin_headers, json={"scope": "article"})

    assert response.status_code == 409
    assert "路径与范围不一致" in response.json()["detail"]
    assert wrong_path.read_bytes() == b"inconsistent"
    assert not (get_settings().media_dir / f"assets/article/{asset['id']}.png").exists()
    with get_session_factory()() as session:
        stored = session.get(Asset, asset["id"])
        assert stored is not None
        assert stored.scope == "user"
        assert stored.storage_path == str(wrong_path)


def test_update_asset_scope_rejects_corrupted_remote_copy_before_switching_database(
    client,
    admin_headers,
    monkeypatch,
):
    from aerisun.domain.media import service as media_service

    deleted: list[str] = []

    class _Provider:
        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            return media_object_storage.ObjectHead(
                content_length=len(data), content_type=content_type, etag="upload", last_modified=utcnow()
            )

        def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None):
            return media_object_storage.ObjectHead(
                content_length=len(b"remote-corrupt"), content_type=content_type, etag="copy", last_modified=utcnow()
            )

        def download_to_local(self, *, object_key: str, dest_path: Path, bandwidth_limit_bps: int | None):
            corrupted = b"xxxxxxxxxxxxxx"
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(corrupted)
            return len(corrupted), "download"

        def delete_object(self, *, object_key: str) -> None:
            deleted.append(object_key)

    provider = _Provider()
    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: provider)
    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: provider)
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: provider)

    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("remote.png", b"remote-corrupt", "image/png")},
        data={"scope": "user", "category": "general"},
    )
    assert created.status_code == 201
    original = created.json()

    response = client.patch(f"{BASE}/{original['id']}", headers=admin_headers, json={"scope": "article"})

    assert response.status_code == 409
    target_key = f"assets/article/{original['id']}.png"
    assert deleted == [target_key]
    with get_session_factory()() as session:
        stored = session.query(Asset).filter_by(id=original["id"]).one()
        assert stored.scope == "user"
        assert stored.storage_path == original["storage_path"]
        assert stored.remote_object_key == f"assets/user/{original['id']}.png"


def test_update_remote_only_asset_visibility_keeps_internal_resource(client, admin_headers, monkeypatch):
    from aerisun.domain.media import service as media_service

    copied: list[tuple[str, str, str | None]] = []
    deleted: list[str] = []

    class _Provider:
        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            return media_object_storage.ObjectHead(
                content_length=len(data),
                content_type=content_type,
                etag="etag-upload",
                last_modified=utcnow(),
            )

        def copy_object(self, *, source_key: str, object_key: str, content_type: str | None = None):
            copied.append((source_key, object_key, content_type))
            return media_object_storage.ObjectHead(
                content_length=12,
                content_type=content_type,
                etag="etag-copy",
                last_modified=utcnow(),
            )

        def delete_object(self, *, object_key: str) -> None:
            deleted.append(object_key)

    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: _Provider())
    monkeypatch.setattr(media_service, "build_object_storage_maintenance_provider", lambda session: _Provider())
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: _Provider())

    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("remote-only.png", b"remote-bytes", "image/png")},
        data={"visibility": "internal", "category": "comment"},
    )
    assert created.status_code == 201
    asset = created.json()
    assert not Path(asset["storage_path"]).exists()

    response = client.patch(
        f"{BASE}/{asset['id']}",
        headers=admin_headers,
        json={"visibility": "public"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["visibility"] == "public"
    assert payload["resource_key"] == asset["resource_key"]
    assert payload["resource_key"] == f"assets/{payload['id']}.png"
    assert payload["internal_url"] == f"/media/{payload['resource_key']}"
    assert payload["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/{payload['resource_key']}"

    with get_session_factory()() as session:
        stored = session.query(Asset).filter_by(id=asset["id"]).one()
        assert stored.remote_object_key == f"assets/user/{payload['id']}.png"
        assert stored.remote_status == "available"

    assert copied == []
    assert deleted == []


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
    assert items[0]["resource_key"] == f"assets/{items[0]['id']}.jpg"
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


def test_init_upload_existing_public_request_keeps_internal_resource(client, admin_headers):
    content = b"existing-bytes"
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("existing.png", content, "image/png")},
        data={"visibility": "internal", "category": "avatar"},
    )
    assert created.status_code == 201
    asset = created.json()

    response = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "existing.png",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mime_type": "image/png",
            "visibility": "public",
            "scope": "user",
            "category": "avatar",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "existing"
    assert payload["asset"]["resource_key"] == asset["resource_key"]
    assert payload["asset"]["internal_url"] == asset["internal_url"]
    assert payload["asset"]["visibility"] == "public"
    assert payload["asset"]["public_url"] == (f"{get_settings().site_url.rstrip('/')}/media/{asset['resource_key']}")


def test_init_upload_existing_resource_can_bind_public_slug(client, admin_headers):
    content = b"existing-bind-slug"
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("existing-bind.png", content, "image/png")},
        data={"visibility": "internal", "category": "avatar"},
    )
    assert created.status_code == 201
    asset = created.json()
    assert asset["public_slug"] is None

    response = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "existing-bind.png",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mime_type": "image/png",
            "visibility": "public",
            "scope": "user",
            "category": "avatar",
            "public_slug": "existing-bind.png",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "existing"
    assert payload["asset"]["id"] == asset["id"]
    assert payload["asset"]["public_slug"] == "existing-bind.png"
    assert payload["asset"]["public_url"] == f"{get_settings().site_url.rstrip('/')}/media/existing-bind.png"


def test_init_upload_existing_resource_rejects_different_public_slug(client, admin_headers):
    content = b"existing-conflict-slug"
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("existing-conflict.png", content, "image/png")},
        data={"visibility": "public", "category": "avatar", "public_slug": "existing-old.png"},
    )
    assert created.status_code == 201

    response = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "existing-conflict.png",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mime_type": "image/png",
            "visibility": "public",
            "scope": "user",
            "category": "avatar",
            "public_slug": "existing-new.png",
        },
    )

    assert response.status_code == 409
    assert "slug" in response.json()["detail"].lower()


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
        assert mirrors[0].object_key == f"assets/user/{payload['id']}.png"


def test_complete_upload_queues_async_mirror_without_writing_local_file(monkeypatch, client, admin_headers):
    from aerisun.domain.media import service as media_service

    content = b"remote-data!"

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
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
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
        assert mirrors[0].object_key == f"assets/user/{payload['asset_id']}.png"


def test_complete_upload_rejects_wrong_remote_size_and_allows_clean_retry(monkeypatch, client, admin_headers):
    from aerisun.domain.media import service as media_service

    deleted: list[str] = []

    class _Provider:
        def sign_upload(self, *, object_key: str, content_type: str | None, expires_in: int) -> str:
            return f"https://upload.example.com/{object_key}"

        def head_object(self, *, object_key: str):
            return media_object_storage.ObjectHead(
                content_length=3,
                content_type="image/png",
                etag="etag-wrong-size",
                last_modified=utcnow(),
            )

        def delete_object(self, *, object_key: str) -> None:
            deleted.append(object_key)

    provider = _Provider()
    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: provider)
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: provider)

    content = b"expected-content"
    plan = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "retry.png",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mime_type": "image/png",
            "visibility": "internal",
            "scope": "user",
            "category": "general",
        },
    )
    assert plan.status_code == 200
    payload = plan.json()

    complete = client.post(
        f"{BASE}/complete-upload",
        headers=admin_headers,
        json={"asset_id": payload["asset_id"]},
    )

    assert complete.status_code == 409
    object_key = f"assets/user/{payload['asset_id']}.png"
    assert deleted == [object_key]
    with get_session_factory()() as session:
        asset = session.get(Asset, payload["asset_id"])
        assert asset is not None
        assert asset.remote_status == "pending_upload"
        assert session.query(AssetMirrorQueueItem).filter_by(asset_id=asset.id).count() == 0

    retry = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "retry.png",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mime_type": "image/png",
            "visibility": "internal",
            "scope": "user",
            "category": "general",
        },
    )
    assert retry.status_code == 200
    assert retry.json()["mode"] == "oss"
    assert retry.json()["asset_id"] == payload["asset_id"]


def test_mirror_download_verifies_sha_before_publishing_local_file(monkeypatch, client, admin_headers):
    from aerisun.domain.media import service as media_service

    content = b"expected-mirror-content"

    class _UploadProvider:
        def sign_upload(self, *, object_key: str, content_type: str | None, expires_in: int) -> str:
            return f"https://upload.example.com/{object_key}"

        def head_object(self, *, object_key: str):
            return media_object_storage.ObjectHead(
                content_length=len(content),
                content_type="image/png",
                etag="etag-upload",
                last_modified=utcnow(),
            )

    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: _UploadProvider())
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: _UploadProvider())

    plan = client.post(
        f"{BASE}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "mirror.png",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "mime_type": "image/png",
            "visibility": "internal",
            "scope": "user",
            "category": "general",
        },
    ).json()
    complete = client.post(
        f"{BASE}/complete-upload",
        headers=admin_headers,
        json={"asset_id": plan["asset_id"]},
    )
    assert complete.status_code == 200
    storage_path = Path(complete.json()["storage_path"])

    class _CorruptMirrorProvider:
        def download_to_local(self, *, object_key: str, dest_path: Path, bandwidth_limit_bps: int | None):
            corrupted = b"x" * len(content)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(corrupted)
            return len(corrupted), "etag-corrupt"

    monkeypatch.setattr(
        media_object_storage,
        "build_object_storage_maintenance_provider",
        lambda session: _CorruptMirrorProvider(),
    )
    media_object_storage.dispatch_due_asset_mirror_jobs()

    assert not storage_path.exists()
    assert not list(storage_path.parent.glob(f".{storage_path.name}.*.mirror.tmp"))
    with get_session_factory()() as session:
        asset = session.get(Asset, plan["asset_id"])
        queue_item = session.query(AssetMirrorQueueItem).filter_by(asset_id=plan["asset_id"]).one()
        assert asset is not None
        assert asset.remote_status == "invalid"
        assert asset.mirror_status == "retrying"
        assert queue_item.status == "retrying"
        assert "摘要" in (queue_item.last_error or "")


def test_admin_open_url_redirects_internal_asset_to_oss_without_proxying(client, admin_headers, monkeypatch):
    created = client.post(
        f"{BASE}/",
        headers=admin_headers,
        files={"file": ("cover.webp", b"cover-bytes", "image/webp")},
        data={"visibility": "internal", "category": "site"},
    )
    assert created.status_code == 201
    asset = created.json()

    from aerisun.api import media as media_api

    monkeypatch.setattr(
        media_api,
        "sign_asset_download_url",
        lambda session, stored_asset: f"https://cdn.example.com/{stored_asset.resource_key}",
    )

    opened = client.post(f"{BASE}/{asset['id']}/open-url", headers=admin_headers)
    assert opened.status_code == 200
    response = client.get(
        opened.json()["url"],
        headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"},
        follow_redirects=False,
    )
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

    response = client.get(
        asset["internal_url"],
        headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "image"},
    )
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
        local_cleanup = session.query(AssetLocalDeleteQueueItem).one()
        assert local_cleanup.storage_path == asset["storage_path"]
        assert local_cleanup.status == "completed"
        queued = session.query(AssetRemoteDeleteQueueItem).all()
        assert len(queued) == 1
        assert queued[0].object_key == asset["resource_key"]
        assert queued[0].status == "retrying"
        assert "delete failed" in (queued[0].last_error or "")


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
        local_cleanup = session.query(AssetLocalDeleteQueueItem).one()
        assert local_cleanup.storage_path == asset["storage_path"]
        assert local_cleanup.status == "completed"
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
        assert queued[0].status == "retrying"


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


def test_local_delete_queue_recovers_cleanup_left_after_database_commit(seeded_session):
    local_path = get_settings().media_dir / "assets/user/recovery-cleanup.png"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(b"cleanup")
    queue_item_id = media_object_storage.queue_local_asset_delete(
        seeded_session,
        storage_path=local_path,
    )
    seeded_session.commit()

    media_object_storage.dispatch_due_local_asset_delete_jobs()

    with get_session_factory()() as session:
        queue_item = media_repo.get_local_delete_queue_item(session, queue_item_id)
        assert queue_item is not None
        assert queue_item.status == "completed"
        assert queue_item.last_error is None
    assert not local_path.exists()


def test_remote_upload_reconcile_and_dispatcher_sync_local_asset(monkeypatch, seeded_session):
    asset_id = "sync-asset"
    local_file = get_settings().media_dir / "assets" / "user" / f"{asset_id}.png"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"sync-bytes")

    asset = Asset(
        id=asset_id,
        file_name="sync.png",
        resource_key=f"assets/{asset_id}.png",
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
        expected_remote_key = f"assets/user/{asset_id}.png"
        assert any(item.object_key == expected_remote_key for item in queued)
        target = next(item for item in queued if item.object_key == expected_remote_key)
        assert target.status == "queued"
        for item in queued:
            if item.object_key != expected_remote_key:
                item.next_retry_at = utcnow() + timedelta(hours=1)
        session.commit()

    media_object_storage.dispatch_due_remote_asset_upload_jobs()

    with get_session_factory()() as session:
        updated = session.query(Asset).filter_by(id=asset.id).first()
        queued = session.query(AssetRemoteUploadQueueItem).filter_by(object_key=expected_remote_key).all()
        assert updated is not None
        assert updated.remote_status == "available"
        assert updated.storage_provider == "bitiful"
        assert updated.remote_etag == "etag-sync"
        assert len(queued) == 1
        assert queued[0].status == "completed"

    assert uploaded == [(expected_remote_key, b"sync-bytes", "image/png")]
