from __future__ import annotations


def test_read_posts_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/site/posts")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=0, must-revalidate"
    assert response.headers["etag"]
    assert response.headers["last-modified"]

    payload = response.json()
    assert len(payload["items"]) == 8
    assert payload["items"][0]["slug"] == "from-zero-design-system"
    assert payload["items"][1]["slug"] == "liquid-glass-css-notes"


def test_read_posts_supports_conditional_get(client) -> None:
    response = client.get("/api/v1/site/posts")

    assert response.status_code == 200

    etag = response.headers["etag"]
    last_modified = response.headers["last-modified"]

    not_modified_by_etag = client.get(
        "/api/v1/site/posts",
        headers={"If-None-Match": etag},
    )
    assert not_modified_by_etag.status_code == 304
    assert not not_modified_by_etag.content

    not_modified_by_last_modified = client.get(
        "/api/v1/site/posts",
        headers={"If-Modified-Since": last_modified},
    )
    assert not_modified_by_last_modified.status_code == 304
    assert not not_modified_by_last_modified.content


def test_read_post_returns_seeded_detail(client) -> None:
    response = client.get("/api/v1/site/posts/from-zero-design-system")

    assert response.status_code == 200

    payload = response.json()
    assert payload["slug"] == "from-zero-design-system"
    assert payload["title"] == "从零搭建个人设计系统的完整思路"
    assert payload["status"] == "published"
    assert payload["visibility"] == "public"


def test_read_post_returns_404_for_unknown_slug(client) -> None:
    response = client.get("/api/v1/site/posts/does-not-exist")

    assert response.status_code == 404
