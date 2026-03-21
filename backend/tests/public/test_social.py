from __future__ import annotations


def test_read_friends_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/public/friends")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 4

    names = [item["name"] for item in payload["items"]]
    assert names == ["Miku's Blog", "AkaraChen", "夏目的博客", "Quiet Terminal"]
    assert "Sunset Archive" not in names
    assert all(item["status"] == "active" for item in payload["items"])
    assert payload["items"][0]["description"] == "记录生活与技术的小站"


def test_read_friend_feed_returns_only_active_enabled_sources(client) -> None:
    response = client.get("/api/v1/public/friend-feed")

    assert response.status_code == 200

    payload = response.json()
    assert [item["blogName"] for item in payload["items"]] == [
        "夏目的博客",
        "Miku's Blog",
        "AkaraChen",
    ]
    assert payload["items"][0]["title"] == "网络流算法详解"
    assert all(item["blogName"] != "Quiet Terminal" for item in payload["items"])
    assert all(item["blogName"] != "Sunset Archive" for item in payload["items"])


def test_read_friend_feed_respects_limit(client) -> None:
    response = client.get("/api/v1/public/friend-feed?limit=2")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["blogName"] == "夏目的博客"
