from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.domain.diary_access.service import DIARY_PRIVATE_FEATURE_FLAG
from aerisun.domain.site_config.models import SiteProfile
from aerisun.domain.subscription.models import ContentNotification, ContentSubscriber
from aerisun.domain.subscription.service import get_subscription_config_orm


def _set_diary_private_enabled(enabled: bool) -> None:
    with get_session_factory()() as session:
        profile = session.query(SiteProfile).one()
        flags = dict(profile.feature_flags or {})
        flags[DIARY_PRIVATE_FEATURE_FLAG] = enabled
        profile.feature_flags = flags
        session.commit()


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


def test_creating_public_diary_does_not_block_on_subscription_dispatch(client, admin_headers, monkeypatch) -> None:
    with get_session_factory()() as session:
        config = get_subscription_config_orm(session)
        config.enabled = True
        config.smtp_test_passed = True
        config.smtp_host = "smtp.example.com"
        config.smtp_port = 587
        config.smtp_from_email = "no-reply@example.com"
        session.add(
            ContentSubscriber(
                email="reader@example.com",
                content_types=["diary"],
                is_active=True,
            )
        )
        session.commit()

    def fail_if_synchronously_dispatched(*args: object, **kwargs: object) -> None:
        raise RuntimeError("subscription dispatch should not run during diary save")

    monkeypatch.setattr(
        "aerisun.domain.subscription.service.dispatch_content_subscription_notifications",
        fail_if_synchronously_dispatched,
    )

    create_response = client.post(
        "/api/v1/admin/diary/",
        json={
            "slug": "diary-subscription-queue-only",
            "title": "订阅只入队的日记",
            "body": "保存日记不应该被邮件发送阻塞。",
            "visibility": "public",
        },
        headers=admin_headers,
    )

    assert create_response.status_code == 201
    with get_session_factory()() as session:
        notification = (
            session.query(ContentNotification)
            .filter(
                ContentNotification.content_type == "diary",
                ContentNotification.content_slug == "diary-subscription-queue-only",
            )
            .first()
        )
        assert notification is not None
        assert notification.delivered_at is None


def test_read_diary_detail_returns_seeded_entry(client) -> None:
    _set_diary_private_enabled(False)
    response = client.get("/api/v1/site/diary/spring-equinox-and-warm-light")

    assert response.status_code == 200

    payload = response.json()
    assert payload["slug"] == "spring-equinox-and-warm-light"
    assert payload["title"] == "春分，天气转暖"
    assert isinstance(payload["body"], str)
    assert payload["body"]


def test_read_diary_detail_returns_404_for_unknown_slug(client) -> None:
    _set_diary_private_enabled(False)
    response = client.get("/api/v1/site/diary/missing-entry")

    assert response.status_code == 404
