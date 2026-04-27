from __future__ import annotations

import os

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.media.models import Asset


def test_media_gateway_serves_local_media_file(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = media_root / "public/assets/test/media-gateway.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("ok", encoding="utf-8")

    response = client.get("/media/public/assets/test/media-gateway.txt")

    assert response.status_code == 200
    assert response.text == "ok"


def test_media_gateway_does_not_force_local_public_media_download(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = media_root / "public/assets/test/inline.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("inline", encoding="utf-8")

    response = client.get("/media/public/assets/test/inline.txt")

    assert response.status_code == 200
    assert "content-disposition" not in response.headers


def test_media_gateway_serves_public_alias_for_registered_internal_asset(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = media_root / "internal/assets/test/public-alias.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("alias", encoding="utf-8")

    factory = get_session_factory()
    with factory() as session:
        session.add(
            Asset(
                file_name="public-alias.txt",
                resource_key="internal/assets/test/public-alias.txt",
                visibility="public",
                scope="user",
                category="test",
                storage_path=str(local_path),
                mime_type="text/plain",
                storage_provider="local",
                remote_status="none",
                mirror_status="completed",
            )
        )
        session.commit()

    response = client.get("/media/public/assets/test/public-alias.txt")

    assert response.status_code == 200
    assert response.text == "alias"
    assert "content-disposition" not in response.headers


def test_media_gateway_rejects_public_alias_for_internal_asset(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = media_root / "internal/assets/test/private-alias.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("private", encoding="utf-8")

    factory = get_session_factory()
    with factory() as session:
        session.add(
            Asset(
                file_name="private-alias.txt",
                resource_key="internal/assets/test/private-alias.txt",
                visibility="internal",
                scope="user",
                category="test",
                storage_path=str(local_path),
                mime_type="text/plain",
                storage_provider="local",
                remote_status="none",
                mirror_status="completed",
            )
        )
        session.commit()

    response = client.get("/media/public/assets/test/private-alias.txt")

    assert response.status_code == 404


def test_media_gateway_serves_internal_alias_for_legacy_public_asset(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = media_root / "public/assets/test/legacy-public.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("legacy", encoding="utf-8")

    factory = get_session_factory()
    with factory() as session:
        session.add(
            Asset(
                file_name="legacy-public.txt",
                resource_key="public/assets/test/legacy-public.txt",
                visibility="public",
                scope="user",
                category="test",
                storage_path=str(local_path),
                mime_type="text/plain",
                storage_provider="local",
                remote_status="none",
                mirror_status="completed",
            )
        )
        session.commit()

    response = client.get("/media/internal/assets/test/legacy-public.txt")

    assert response.status_code == 200
    assert response.text == "legacy"


def test_media_gateway_rejects_unregistered_internal_media_file(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = media_root / "internal/assets/test/unregistered.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("do-not-read", encoding="utf-8")

    response = client.get("/media/internal/assets/test/unregistered.txt")

    assert response.status_code == 404


def test_media_gateway_blocks_path_traversal(client, tmp_path) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    outside_file = tmp_path / "outside-secret.txt"
    outside_file.write_text("do-not-read", encoding="utf-8")

    traversal = os.path.relpath(outside_file, media_root).replace(os.sep, "/")
    response = client.get(f"/media/{traversal}")

    assert response.status_code == 404


def test_media_gateway_rejects_asset_storage_path_outside_media_root(client, tmp_path) -> None:
    outside_file = tmp_path / "db-path-secret.txt"
    outside_file.write_text("do-not-read", encoding="utf-8")

    factory = get_session_factory()
    with factory() as session:
        session.add(
            Asset(
                file_name="db-path-secret.txt",
                resource_key="internal/assets/test/db-path-secret.txt",
                visibility="internal",
                scope="user",
                category="test",
                storage_path=str(outside_file),
                storage_provider="local",
                remote_status="none",
                mirror_status="completed",
            )
        )
        session.commit()

    response = client.get("/media/internal/assets/test/db-path-secret.txt")

    assert response.status_code == 404
