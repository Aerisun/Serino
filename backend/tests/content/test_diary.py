from __future__ import annotations


def test_read_diary_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/site/diary")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 7
    assert payload["items"][0]["slug"] == "spring-equinox-and-warm-light"
    assert "body" not in payload["items"][0]


def test_read_diary_summary_list_preserves_body_excerpt_fallback(client, admin_headers) -> None:
    body = "这是旧日记列表会显示的第一段。\n\n第二段只应该留给详情页。"
    create_response = client.post(
        "/api/v1/admin/diary/",
        json={
            "slug": "diary-without-summary",
            "title": "未填写摘要的日记",
            "body": body,
            "visibility": "public",
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 201

    response = client.get("/api/v1/site/diary?limit=100")

    assert response.status_code == 200
    entry = next(item for item in response.json()["items"] if item["slug"] == "diary-without-summary")
    assert entry["summary"] == "这是旧日记列表会显示的第一段。"
    assert "body" not in entry


def test_read_diary_detail_returns_seeded_entry(client) -> None:
    response = client.get("/api/v1/site/diary/spring-equinox-and-warm-light")

    assert response.status_code == 200

    payload = response.json()
    assert payload["slug"] == "spring-equinox-and-warm-light"
    assert payload["title"] == "春分，天气转暖"
    assert isinstance(payload["body"], str)
    assert payload["body"]


def test_read_diary_detail_returns_404_for_unknown_slug(client) -> None:
    response = client.get("/api/v1/site/diary/missing-entry")

    assert response.status_code == 404
