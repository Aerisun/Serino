from __future__ import annotations

from aerisun.core.settings import get_settings

BASE = "/api/v1/admin/integrations"


def test_list_feeds_returns_canonical_public_content_feeds(client, admin_headers) -> None:
    site_url = (get_settings().site_url or "https://example.com").rstrip("/")

    response = client.get(f"{BASE}/feeds", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == [
        {
            "key": "posts",
            "title": "Aerisun Posts",
            "url": f"{site_url}/feeds/posts.xml",
            "enabled": True,
            "format": "rss",
        },
        {
            "key": "diary",
            "title": "Aerisun Diary",
            "url": f"{site_url}/feeds/diary.xml",
            "enabled": True,
            "format": "rss",
        },
        {
            "key": "thoughts",
            "title": "Aerisun Thoughts",
            "url": f"{site_url}/feeds/thoughts.xml",
            "enabled": True,
            "format": "rss",
        },
        {
            "key": "excerpts",
            "title": "Aerisun Excerpts",
            "url": f"{site_url}/feeds/excerpts.xml",
            "enabled": True,
            "format": "rss",
        },
    ]
