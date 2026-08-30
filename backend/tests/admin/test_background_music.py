from __future__ import annotations

from pathlib import Path

from aerisun.core.db import get_session_factory
from aerisun.domain.media.models import Asset

BASE = "/api/v1/admin/site-config/background-music"
ASSETS = "/api/v1/admin/assets"


def _upload_music_asset(
    client,
    admin_headers,
    *,
    file_name: str = "Moonlight.Theme.mp3",
    content: bytes = b"ID3-test-audio",
    mime_type: str = "audio/mpeg",
) -> dict:
    response = client.post(
        f"{ASSETS}/",
        headers=admin_headers,
        files={"file": (file_name, content, mime_type)},
        data={
            "visibility": "public",
            "scope": "system",
            "category": "music",
            "note": "背景音乐",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_track(client, admin_headers, asset_id: str, *, title: str | None = None) -> dict:
    payload = {"asset_id": asset_id}
    if title is not None:
        payload["title"] = title
    response = client.post(f"{BASE}/tracks", headers=admin_headers, json=payload)
    assert response.status_code == 201
    return response.json()


def test_background_music_defaults_to_disabled_sequential_empty_playlist(client, admin_headers) -> None:
    response = client.get(BASE, headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "playback_mode": "sequential",
        "tracks": [],
    }


def test_background_music_cannot_be_enabled_without_a_playable_track(client, admin_headers) -> None:
    response = client.put(
        BASE,
        headers=admin_headers,
        json={"enabled": True, "playback_mode": "random"},
    )

    assert response.status_code == 422
    assert "曲目" in response.json()["detail"]


def test_background_music_track_uses_filename_as_default_title_and_enters_public_bootstrap(
    client,
    admin_headers,
) -> None:
    asset = _upload_music_asset(client, admin_headers)
    track = _create_track(client, admin_headers, asset["id"])

    assert track["title"] == "Moonlight.Theme"
    assert track["file_name"] == "Moonlight.Theme.mp3"
    assert track["byte_size"] == len(b"ID3-test-audio")
    assert track["mime_type"] == "audio/mpeg"
    assert track["is_enabled"] is True
    assert track["order_index"] == 0
    assert track["stream_url"] == asset["internal_url"]

    enabled = client.put(
        BASE,
        headers=admin_headers,
        json={"enabled": True, "playback_mode": "random"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert enabled.json()["playback_mode"] == "random"

    bootstrap = client.get("/api/v1/site/bootstrap")
    assert bootstrap.status_code == 200
    assert bootstrap.headers["cache-control"] == "public, max-age=0, must-revalidate"
    assert bootstrap.headers["etag"]
    assert bootstrap.json()["background_music"] == {
        "enabled": True,
        "playback_mode": "random",
        "tracks": [
            {
                "id": track["id"],
                "title": "Moonlight.Theme",
                "stream_url": asset["internal_url"],
            }
        ],
    }


def test_background_music_tracks_can_be_edited_disabled_and_reordered(client, admin_headers) -> None:
    first_asset = _upload_music_asset(
        client,
        admin_headers,
        file_name="First.mp3",
        content=b"ID3-first",
    )
    second_asset = _upload_music_asset(
        client,
        admin_headers,
        file_name="Second.m4a",
        content=b"m4a-second",
        mime_type="audio/mp4",
    )
    first = _create_track(client, admin_headers, first_asset["id"])
    second = _create_track(client, admin_headers, second_asset["id"], title="第二首")

    reordered = client.put(
        f"{BASE}/tracks/reorder",
        headers=admin_headers,
        json={"track_ids": [second["id"], first["id"]]},
    )
    assert reordered.status_code == 200
    assert [item["id"] for item in reordered.json()["tracks"]] == [second["id"], first["id"]]
    assert [item["order_index"] for item in reordered.json()["tracks"]] == [0, 1]

    updated = client.patch(
        f"{BASE}/tracks/{second['id']}",
        headers=admin_headers,
        json={"title": "新的歌名", "is_enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "新的歌名"
    assert updated.json()["is_enabled"] is False

    enabled = client.put(
        BASE,
        headers=admin_headers,
        json={"enabled": True, "playback_mode": "sequential"},
    )
    assert enabled.status_code == 200
    public_music = client.get("/api/v1/site/bootstrap").json()["background_music"]
    assert public_music["enabled"] is True
    assert [item["id"] for item in public_music["tracks"]] == [first["id"]]


def test_active_music_track_prevents_direct_asset_deletion(client, admin_headers) -> None:
    asset = _upload_music_asset(client, admin_headers)
    _create_track(client, admin_headers, asset["id"])

    response = client.delete(f"{ASSETS}/{asset['id']}", headers=admin_headers)

    assert response.status_code == 409
    assert "background_music_tracks.asset_id" in response.json()["detail"]


def test_deleting_music_track_also_deletes_its_dedicated_asset(client, admin_headers) -> None:
    asset = _upload_music_asset(client, admin_headers)
    track = _create_track(client, admin_headers, asset["id"])
    storage_path = Path(asset["storage_path"])
    assert storage_path.is_file()

    response = client.delete(f"{BASE}/tracks/{track['id']}", headers=admin_headers)

    assert response.status_code == 204
    with get_session_factory()() as session:
        assert session.get(Asset, asset["id"]) is None
    assert not storage_path.exists()


def test_music_upload_plan_rejects_unsupported_format_and_oversized_file(client, admin_headers) -> None:
    unsupported = client.post(
        f"{ASSETS}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "track.wav",
            "byte_size": 1024,
            "sha256": "a" * 64,
            "mime_type": "audio/wav",
            "visibility": "public",
            "scope": "system",
            "category": "music",
        },
    )
    oversized = client.post(
        f"{ASSETS}/init-upload",
        headers=admin_headers,
        json={
            "file_name": "track.mp3",
            "byte_size": 50 * 1024 * 1024 + 1,
            "sha256": "b" * 64,
            "mime_type": "audio/mpeg",
            "visibility": "public",
            "scope": "system",
            "category": "music",
        },
    )

    assert unsupported.status_code == 422
    assert "MP3" in unsupported.json()["detail"]
    assert oversized.status_code == 413
    assert "50" in oversized.json()["detail"]


def test_music_track_rejects_non_music_or_internal_asset(client, admin_headers) -> None:
    response = client.post(
        f"{ASSETS}/",
        headers=admin_headers,
        files={"file": ("not-music.mp3", b"ID3-private", "audio/mpeg")},
        data={"visibility": "internal", "scope": "system", "category": "general"},
    )
    assert response.status_code == 201

    attached = client.post(
        f"{BASE}/tracks",
        headers=admin_headers,
        json={"asset_id": response.json()["id"]},
    )

    assert attached.status_code == 422
    assert "公开音乐资源" in attached.json()["detail"]
