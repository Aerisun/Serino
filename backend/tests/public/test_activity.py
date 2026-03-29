from __future__ import annotations

from datetime import UTC, datetime

import aerisun.domain.activity.service as activity_service


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        current = cls(2026, 3, 27, 12, tzinfo=UTC)
        return current if tz is None else current.astimezone(tz)


def test_read_calendar_returns_content_events(client) -> None:
    response = client.get("/api/v1/site/calendar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["events"]
    assert payload["events"][0]["type"] in {"post", "diary", "excerpt"}


def test_read_recent_activity_returns_items(client) -> None:
    response = client.get("/api/v1/site/recent-activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["kind"] in {"comment", "reply", "like", "guestbook"}


def test_read_activity_heatmap_returns_weeks(client) -> None:
    response = client.get("/api/v1/site/activity-heatmap?weeks=12")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["weeks"]) == 12
    assert "total_contributions" in payload["stats"]


def test_read_activity_heatmap_includes_thoughts_and_likes_in_shanghai_timezone(client, monkeypatch) -> None:
    monkeypatch.setattr(activity_service, "datetime", _FixedDateTime)

    response = client.get("/api/v1/site/activity-heatmap?weeks=12")
    explicit_response = client.get("/api/v1/site/activity-heatmap?weeks=12&tz=Asia/Shanghai")

    assert response.status_code == 200
    assert explicit_response.status_code == 200
    payload = response.json()
    assert payload == explicit_response.json()
    assert isinstance(payload["stats"]["average_per_week"], float)
    assert payload["stats"]["average_per_week"] == round(payload["stats"]["total_contributions"] / 12, 1)
    assert payload["stats"]["peak_week"] == max(week["total"] for week in payload["weeks"])
    assert payload["stats"]["peak_week"] >= 15
    assert payload["weeks"][-1]["week_start"] == "2026-03-23"
    assert payload["weeks"][-1]["total"] == 3
    days = payload["weeks"][-1]["days"]
    assert len(days) == 7
    assert sum(days) == 3
    assert sorted(days) == [0, 0, 0, 0, 0, 0, 3]
