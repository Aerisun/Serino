from __future__ import annotations


def test_read_guestbook_returns_seeded_entries(client) -> None:
    response = client.get("/api/v1/public/guestbook")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 0


def test_create_guestbook_accepts_pending_entry(client) -> None:
    response = client.post(
        "/api/v1/public/guestbook",
        json={
            "name": "Test Guest",
            "email": "guest@example.com",
            "website": "https://guest.example.com",
            "body": "Hello from pytest.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["status"] == "pending"


def test_read_comments_returns_nested_items(client) -> None:
    response = client.get("/api/v1/public/comments/posts/from-zero-design-system")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 0


def test_create_comment_accepts_pending_item(client) -> None:
    response = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Pytest Reader",
            "author_email": "reader@example.com",
            "body": "很喜欢这篇。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["status"] == "pending"


def test_create_reaction_returns_total(client) -> None:
    response = client.post(
        "/api/v1/public/reactions",
        json={
            "content_type": "posts",
            "content_slug": "from-zero-design-system",
            "reaction_type": "like",
            "client_token": "pytest-token",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reaction_type"] == "like"
    assert payload["total"] >= 3
