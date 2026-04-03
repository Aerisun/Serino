from __future__ import annotations


def test_read_friends_returns_seeded_collection(client) -> None:
    response = client.get("/api/v1/site/friends")

    assert response.status_code == 200

    payload = response.json()
    assert len(payload["items"]) == 1

    names = {item["name"] for item in payload["items"]}
    assert names == {"Arthals' ink"}
    assert all(item["status"] == "active" for item in payload["items"])
    by_name = {item["name"]: item for item in payload["items"]}
    assert by_name["Arthals' ink"]["description"] == "所见高山远木，阔云流风；所幸岁月盈余，了无拘束"
    assert by_name["Arthals' ink"]["url"] == "https://arthals.ink/"
    assert by_name["Arthals' ink"]["avatar"] == "https://cdn.arthals.ink/Arthals.png"


def test_read_friend_feed_returns_only_active_enabled_sources(client) -> None:
    response = client.get("/api/v1/site/friend-feed")

    assert response.status_code == 200

    payload = response.json()
    assert payload["items"] == []


def test_read_friend_feed_respects_limit(client) -> None:
    response = client.get("/api/v1/site/friend-feed?limit=2")

    assert response.status_code == 200

    payload = response.json()
    assert payload["items"] == []
