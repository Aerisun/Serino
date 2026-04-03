from __future__ import annotations


def test_site_profile_media_links_are_not_restricted(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/site-config/profile",
        headers=admin_headers,
        json={
            "hero_image_url": "https://example.com/hero.webp",
            "hero_video_url": "https://example.com/hero.mp4",
            "site_icon_url": "/images/custom-icon.svg",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hero_image_url"] == "https://example.com/hero.webp"
    assert payload["hero_video_url"] == "https://example.com/hero.mp4"
    assert payload["site_icon_url"] == "/images/custom-icon.svg"


def test_site_profile_registered_media_urls_still_work(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/site-config/profile",
        headers=admin_headers,
        json={"site_icon_url": "/media/internal/assets/site-icon/test.svg"},
    )

    assert response.status_code == 200
    assert response.json()["site_icon_url"] == "/media/internal/assets/site-icon/test.svg"


def test_resume_avatar_links_are_not_restricted(client, admin_headers) -> None:
    basics_response = client.get("/api/v1/admin/resume/basics/", headers=admin_headers)
    assert basics_response.status_code == 200
    basics_id = basics_response.json()["items"][0]["id"]

    response = client.put(
        f"/api/v1/admin/resume/basics/{basics_id}",
        headers=admin_headers,
        json={"profile_image_url": "https://example.com/avatar.png"},
    )

    assert response.status_code == 200
    assert response.json()["profile_image_url"] == "https://example.com/avatar.png"


def test_page_copy_rejects_page_size_above_thirty(client, admin_headers) -> None:
    listing = client.get("/api/v1/admin/site-config/page-copy/", headers=admin_headers)
    assert listing.status_code == 200
    posts_copy = next(item for item in listing.json()["items"] if item["page_key"] == "posts")

    response = client.put(
        f"/api/v1/admin/site-config/page-copy/{posts_copy['id']}",
        headers=admin_headers,
        json={"page_size": 31},
    )

    assert response.status_code == 422
