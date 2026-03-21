from __future__ import annotations


def test_read_calendar_returns_content_events(client) -> None:
    response = client.get("/api/v1/public/calendar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["events"]
    assert payload["events"][0]["type"] in {"post", "diary", "excerpt"}


def test_read_recent_activity_returns_items(client) -> None:
    response = client.get("/api/v1/public/recent-activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["kind"] in {"comment", "reply", "like", "guestbook"}


def test_read_activity_heatmap_returns_weeks(client) -> None:
    response = client.get("/api/v1/public/activity-heatmap?weeks=12")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["weeks"]) == 12
    assert "total_contributions" in payload["stats"]
