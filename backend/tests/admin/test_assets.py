from __future__ import annotations

from pathlib import Path

from aerisun.core.settings import get_settings

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
