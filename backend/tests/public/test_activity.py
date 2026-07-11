from __future__ import annotations

from datetime import datetime

import aerisun.domain.activity.service as activity_service
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.core.time import BEIJING_TZ
from aerisun.domain.content.models import DiaryEntry, PostEntry, ThoughtEntry
from aerisun.domain.diary_access.service import DIARY_PRIVATE_FEATURE_FLAG
from aerisun.domain.engagement.models import Reaction
from aerisun.domain.site_config.models import SiteProfile
from aerisun.domain.waline.service import connect_waline_db


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        current = cls(2026, 3, 27, 12, tzinfo=BEIJING_TZ)
        return current if tz is None else current.astimezone(tz)


def test_read_calendar_returns_content_events(client) -> None:
    response = client.get("/api/v1/site/calendar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["events"]
    assert payload["events"][0]["type"] in {"post", "diary", "excerpt"}


def test_read_calendar_uses_beijing_date_boundary(client) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            PostEntry(
                slug="beijing-boundary-post",
                title="Beijing Boundary",
                body="Boundary body",
                summary="Boundary summary",
                visibility="public",
                published_at=datetime(2026, 4, 1, 0, 30, tzinfo=BEIJING_TZ),
            )
        )
        session.commit()

    response = client.get("/api/v1/site/calendar?from=2026-04-01&to=2026-04-01")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["title"] == "Beijing Boundary" and item["date"] == "2026-04-01" for item in payload["events"])


def test_read_recent_activity_returns_items(client) -> None:
    response = client.get("/api/v1/site/recent-activity")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=0, must-revalidate"
    assert response.headers["etag"]
    payload = response.json()
    assert payload["items"]
    assert any(item["kind"].startswith("publish_") for item in payload["items"])
    assert payload["items"][0]["kind"] in {"comment", "reply", "like", "guestbook"} or payload["items"][0][
        "kind"
    ].startswith("publish_")

    cached_response = client.get(
        "/api/v1/site/recent-activity",
        headers={"If-None-Match": response.headers["etag"]},
    )
    assert cached_response.status_code == 304


def test_read_recent_activity_falls_back_to_published_content_when_no_interactions(client) -> None:
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        session.query(Reaction).delete()
        session.commit()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        connection.commit()

    response = client.get("/api/v1/site/recent-activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert all(item["kind"].startswith("publish_") for item in payload["items"])
    assert any((item["target_title"] or item["excerpt"]) for item in payload["items"])


def test_read_recent_activity_includes_latest_public_thought(client) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            ThoughtEntry(
                slug="latest-public-thought",
                title="Latest public thought",
                body="A fresh thought with an image ![diagram](/media/diagram.png)",
                summary=None,
                tags=[],
                visibility="public",
                published_at=datetime(2099, 7, 10, 12, tzinfo=BEIJING_TZ),
            )
        )
        session.commit()

    response = client.get("/api/v1/site/recent-activity?limit=1")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["kind"] == "publish_thought"
    assert item["target_title"] == ""
    assert item["excerpt"] == "A fresh thought with an image"
    assert item["created_at"] == "2099-07-10T12:00:00+08:00"
    assert item["href"] == "/thoughts#latest-public-thought"


def test_read_recent_activity_excludes_owner_comments_for_unselected_content_types(client) -> None:
    from aerisun.domain.site_auth.models import SiteAdminIdentity, SiteUser
    from aerisun.domain.waline.service import create_waline_record

    owner_email = "activity-owner@example.com"
    session_factory = get_session_factory()
    with session_factory() as session:
        owner = SiteUser(
            email=owner_email,
            display_name="Activity Owner",
            avatar_url="",
        )
        session.add(owner)
        session.flush()
        session.add(
            SiteAdminIdentity(
                site_user_id=owner.id,
                provider="email",
                identifier=owner_email,
                email=owner_email,
            )
        )
        profile = session.query(SiteProfile).one()
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            "recent_activity_owner_comment_content_types": ["thoughts"],
        }
        session.commit()

    create_waline_record(
        comment="Owner post comment should be hidden",
        nick="Activity Owner",
        mail=owner_email,
        link=None,
        status="approved",
        url="/posts/from-zero-design-system",
    )
    create_waline_record(
        comment="Owner thought comment should be shown",
        nick="Activity Owner",
        mail=owner_email,
        link=None,
        status="approved",
        url="/thoughts/spacing-rhythm-note",
    )
    create_waline_record(
        comment="Visitor post comment should stay visible",
        nick="Visitor",
        mail="visitor@example.com",
        link=None,
        status="approved",
        url="/posts/from-zero-design-system",
    )

    response = client.get("/api/v1/site/recent-activity?limit=8")

    assert response.status_code == 200
    items = response.json()["items"]
    assert not any(item["excerpt"] == "Owner post comment should be hidden" for item in items)
    assert any(item["excerpt"] == "Owner thought comment should be shown" for item in items)
    assert any(item["excerpt"] == "Visitor post comment should stay visible" for item in items)
    assert any(item["kind"].startswith("publish_") for item in items)


def test_read_recent_activity_keeps_private_diary_publish_visible_with_preview(client) -> None:
    entries = [
        (
            "private-recent-activity-diary",
            "Hidden Diary Title",
            "Hidden diary summary",
            "Hidden diary body",
            datetime(2026, 4, 2, 12, tzinfo=BEIJING_TZ),
        ),
        (
            "private-recent-activity-body-only-diary",
            "Body Only Diary Title",
            None,
            "Body-only diary secret should never appear in recent activity.",
            datetime(2026, 4, 3, 12, tzinfo=BEIJING_TZ),
        ),
    ]
    session_factory = get_session_factory()
    with session_factory() as session:
        profile = session.query(SiteProfile).one()
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            DIARY_PRIVATE_FEATURE_FLAG: True,
        }
        session.add_all(
            DiaryEntry(
                slug=slug,
                title=title,
                summary=summary,
                body=body,
                tags=[],
                visibility="public",
                published_at=published_at,
            )
            for slug, title, summary, body, published_at in entries
        )
        session.commit()

    response = client.get("/api/v1/site/recent-activity?limit=8")

    assert response.status_code == 200
    items_by_href = {item["href"]: item for item in response.json()["items"]}
    for slug, title, summary, body, _published_at in entries:
        item = items_by_href[f"/diary/{slug}"]
        assert (item["kind"], item["target_title"], item["excerpt"]) == ("publish_diary", title, summary)
        assert body not in response.text


def test_read_activity_heatmap_returns_weeks(client) -> None:
    activity_service._heatmap_cache.clear()
    response = client.get("/api/v1/site/activity-heatmap?weeks=12")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["weeks"]) == 12
    assert "total_contributions" in payload["stats"]


def test_activity_heatmap_refreshes_after_public_post_is_published(client, admin_headers) -> None:
    activity_service._heatmap_cache.clear()
    initial_response = client.get("/api/v1/site/activity-heatmap?weeks=52")

    assert initial_response.status_code == 200
    initial_total = initial_response.json()["stats"]["total_contributions"]
    assert activity_service._heatmap_cache

    publish_response = client.post(
        "/api/v1/admin/posts/",
        headers=admin_headers,
        json={
            "slug": "heatmap-cache-refresh-post",
            "title": "Heatmap Cache Refresh",
            "body": "Publishing this post must refresh the activity heatmap.",
            "visibility": "public",
        },
    )

    assert publish_response.status_code == 201
    assert not activity_service._heatmap_cache

    refreshed_response = client.get("/api/v1/site/activity-heatmap?weeks=52")

    assert refreshed_response.status_code == 200
    assert refreshed_response.json()["stats"]["total_contributions"] == initial_total + 1


def test_read_activity_heatmap_includes_thoughts_and_likes_in_shanghai_timezone(client, monkeypatch) -> None:
    activity_service._heatmap_cache.clear()
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
    assert payload["weeks"][-1]["total"] == 0
    days = payload["weeks"][-1]["days"]
    assert len(days) == 7
    assert sum(days) == 0
    assert sorted(days) == [0, 0, 0, 0, 0, 0, 0]
    assert payload["weeks"][-2]["week_start"] == "2026-03-16"
    assert payload["weeks"][-2]["total"] == 17
