from __future__ import annotations


def test_read_pages_returns_seeded_page_copy(client) -> None:
    response = client.get("/api/v1/public/pages")

    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload["items"], list)

    items = {item["page_key"]: item for item in payload["items"]}
    assert items["posts"]["title"] == "Posts"
    assert items["friends"]["page_size"] == 10
    assert items["resume"]["download_label"] == "下载 PDF"
    assert "enabled" in items["posts"]
