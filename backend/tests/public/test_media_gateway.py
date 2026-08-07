from __future__ import annotations

import os
from pathlib import Path

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.media.models import Asset


def _create_asset(
    *,
    asset_id: str,
    visibility: str,
    content: bytes,
    public_slug: str | None = None,
    storage_path: Path | None = None,
) -> Asset:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = storage_path or media_root / f"assets/user/{asset_id}.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    asset = Asset(
        id=asset_id,
        file_name=f"{asset_id}.txt",
        resource_key=f"assets/{asset_id}.txt",
        public_slug=public_slug,
        visibility=visibility,
        scope="user",
        category="general",
        storage_path=str(local_path),
        mime_type="text/plain",
        byte_size=len(content),
        storage_provider="local",
        remote_status="none",
        mirror_status="completed",
    )
    factory = get_session_factory()
    with factory() as session:
        session.add(asset)
        session.commit()
        session.expunge(asset)
    return asset


def test_media_gateway_serves_public_asset_from_canonical_url_on_direct_navigation(client) -> None:
    _create_asset(asset_id="public-asset", visibility="public", content=b"public")

    response = client.get(
        "/media/assets/public-asset.txt",
        headers={"Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"},
    )

    assert response.status_code == 200
    assert response.content == b"public"
    assert "content-disposition" not in response.headers


def test_media_gateway_serves_internal_asset_as_same_origin_subresource(client) -> None:
    _create_asset(asset_id="internal-image", visibility="internal", content=b"internal")

    response = client.get(
        "/media/assets/internal-image.txt",
        headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "image"},
    )

    assert response.status_code == 200
    assert response.content == b"internal"
    assert response.headers["cache-control"] == "private, no-store"
    vary = {item.strip().lower() for item in response.headers["vary"].split(",")}
    assert {"sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest"}.issubset(vary)


def test_media_gateway_rejects_internal_asset_direct_navigation(client) -> None:
    _create_asset(asset_id="internal-direct", visibility="internal", content=b"internal")

    response = client.get(
        "/media/assets/internal-direct.txt",
        headers={"Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"},
    )

    assert response.status_code == 403


def test_media_gateway_rejects_internal_asset_cross_site_hotlink(client) -> None:
    _create_asset(asset_id="internal-hotlink", visibility="internal", content=b"internal")

    response = client.get(
        "/media/assets/internal-hotlink.txt",
        headers={"Sec-Fetch-Site": "cross-site", "Referer": "https://outside.example/page"},
    )

    assert response.status_code == 403


def test_media_gateway_allows_internal_asset_with_exact_site_referer_when_fetch_metadata_missing(client) -> None:
    _create_asset(asset_id="internal-fallback", visibility="internal", content=b"internal")

    response = client.get(
        "/media/assets/internal-fallback.txt",
        headers={"Referer": f"{get_settings().site_url.rstrip('/')}/posts/example"},
    )

    assert response.status_code == 200


def test_media_gateway_rejects_internal_asset_without_fetch_metadata_or_trusted_origin(client) -> None:
    _create_asset(asset_id="internal-unknown", visibility="internal", content=b"internal")

    response = client.get("/media/assets/internal-unknown.txt")

    assert response.status_code == 403


def test_media_gateway_serves_public_slug_but_never_internal_slug(client) -> None:
    _create_asset(asset_id="public-slug-asset", visibility="public", content=b"public slug", public_slug="readme.txt")
    _create_asset(
        asset_id="internal-slug-asset",
        visibility="internal",
        content=b"internal slug",
        public_slug="private-readme.txt",
    )

    public_response = client.get("/media/readme.txt")
    internal_response = client.get(
        "/media/private-readme.txt",
        headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Dest": "image"},
    )

    assert public_response.status_code == 200
    assert public_response.content == b"public slug"
    assert internal_response.status_code == 404


def test_media_gateway_rejects_all_legacy_internal_and_public_routes(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    legacy_path = media_root / "internal/assets/test/legacy.txt"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(b"legacy")
    factory = get_session_factory()
    with factory() as session:
        session.add(
            Asset(
                id="legacy-asset",
                file_name="legacy.txt",
                resource_key="internal/assets/test/legacy.txt",
                visibility="public",
                scope="user",
                category="test",
                storage_path=str(legacy_path),
                mime_type="text/plain",
                storage_provider="local",
                remote_status="none",
                mirror_status="completed",
            )
        )
        session.commit()

    assert client.get("/media/internal/assets/test/legacy.txt").status_code == 404
    assert client.get("/media/public/assets/test/legacy.txt").status_code == 404


def test_media_gateway_rejects_unregistered_canonical_file(client) -> None:
    media_root = get_settings().media_dir.expanduser().resolve()
    local_path = media_root / "assets/user/unregistered.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("do-not-read", encoding="utf-8")

    response = client.get("/media/assets/unregistered.txt")

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
    _create_asset(
        asset_id="outside-path",
        visibility="public",
        content=b"do-not-read",
        storage_path=outside_file,
    )

    response = client.get("/media/assets/outside-path.txt")

    assert response.status_code == 404
