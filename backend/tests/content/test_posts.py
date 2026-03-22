from __future__ import annotations


def test_read_posts_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/public/posts")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 8
    assert payload["items"][0]["slug"] == "from-zero-design-system"
    assert payload["items"][1]["slug"] == "liquid-glass-css-notes"


def test_read_post_returns_seeded_detail(client) -> None:
    response = client.get("/api/v1/public/posts/from-zero-design-system")

    assert response.status_code == 200

    payload = response.json()
    assert payload["slug"] == "from-zero-design-system"
    assert payload["title"] == "从零搭建个人设计系统的完整思路"
    assert payload["status"] == "published"
    assert payload["visibility"] == "public"


def test_read_post_returns_404_for_unknown_slug(client) -> None:
    response = client.get("/api/v1/public/posts/does-not-exist")

    assert response.status_code == 404
