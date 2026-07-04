from __future__ import annotations

from datetime import timedelta

from aerisun.core.db import get_session_factory
from aerisun.core.time import shanghai_now
from aerisun.domain.site_auth.models import SiteUser
from aerisun.domain.site_config.models import SiteProfile
from aerisun.domain.subscription.models import ContentSubscriber
from aerisun.domain.subscription.service import get_subscription_config_orm

DIARY_SLUG = "spring-equinox-and-warm-light"
DIARY_DETAIL_PATH = f"/api/v1/site/diary/{DIARY_SLUG}"


def _login_site_user(client, *, email: str = "diary-reader@example.com", display_name: str = "Diary Reader") -> None:
    response = client.post(
        "/api/v1/site-auth/email",
        json={
            "email": email,
            "display_name": display_name,
            "avatar_url": f"https://api.dicebear.com/9.x/notionists/svg?seed={display_name}",
        },
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def _set_diary_private_enabled(enabled: bool) -> None:
    with get_session_factory()() as session:
        profile = session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
        assert profile is not None
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            "diary_private_enabled": enabled,
        }
        session.commit()


def _configure_smtp(*, test_passed: bool) -> None:
    with get_session_factory()() as session:
        config = get_subscription_config_orm(session)
        config.smtp_auth_mode = "password"
        config.smtp_host = "localhost"
        config.smtp_port = 1025
        config.smtp_from_email = "owner@example.com"
        config.smtp_username = ""
        config.smtp_password = ""
        config.smtp_test_passed = test_passed
        config.smtp_tested_at = None
        session.commit()


def test_diary_detail_is_private_by_default_and_lists_remain_public(client) -> None:
    list_response = client.get("/api/v1/site/diary")
    detail_response = client.get(DIARY_DETAIL_PATH)

    assert list_response.status_code == 200
    assert any(item["slug"] == DIARY_SLUG for item in list_response.json()["items"])
    assert detail_response.status_code == 401
    assert detail_response.json()["detail"] == "请先登录。"


def test_logged_in_user_without_diary_access_receives_forbidden(client) -> None:
    _login_site_user(client)

    state_response = client.get("/api/v1/site/diary-access/me")
    detail_response = client.get(DIARY_DETAIL_PATH)

    assert state_response.status_code == 200
    assert state_response.json()["authenticated"] is True
    assert state_response.json()["has_access"] is False
    assert state_response.json()["diary_private_enabled"] is True
    assert state_response.json()["mail_feedback_available"] is False
    assert detail_response.status_code == 403
    assert detail_response.json()["detail"] == "您没有权限查看 Aerisun 的日记"


def test_diary_access_state_hides_mail_feedback_until_smtp_test_passes(client) -> None:
    _configure_smtp(test_passed=False)

    response = client.get("/api/v1/site/diary-access/me")

    assert response.status_code == 200
    assert response.json()["mail_feedback_available"] is False


def test_diary_access_state_reports_mail_feedback_after_smtp_test_passes(client) -> None:
    _configure_smtp(test_passed=True)

    response = client.get("/api/v1/site/diary-access/me")

    assert response.status_code == 200
    assert response.json()["mail_feedback_available"] is True


def test_diary_access_request_can_be_submitted_approved_and_revoked(client, admin_headers) -> None:
    _login_site_user(client)

    first_request = client.post(
        "/api/v1/site/diary-access/requests",
        json={"reason": "想完整阅读这些日记。"},
    )
    second_request = client.post(
        "/api/v1/site/diary-access/requests",
        json={"reason": "补充理由：我会尊重隐私。"},
    )

    assert first_request.status_code == 201
    assert second_request.status_code == 201
    assert second_request.json()["id"] == first_request.json()["id"]
    assert second_request.json()["reason"] == "补充理由：我会尊重隐私。"

    list_response = client.get(
        "/api/v1/admin/moderation/diary-access-requests",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["visitor_email"] == "diary-reader@example.com"
    assert item["visitor_auth_provider"] == "email"
    assert item["has_access"] is False
    assert item["reason"] == "补充理由：我会尊重隐私。"

    expires_at = (shanghai_now() + timedelta(days=7)).isoformat()
    approve_response = client.patch(
        f"/api/v1/admin/moderation/diary-access-requests/{item['id']}",
        json={"grant_access": True, "expires_at": expires_at},
        headers=admin_headers,
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["has_access"] is True
    assert approve_response.json()["access_expires_at"] is not None

    allowed_detail = client.get(DIARY_DETAIL_PATH)
    assert allowed_detail.status_code == 200
    assert allowed_detail.json()["slug"] == DIARY_SLUG

    with get_session_factory()() as session:
        user = session.query(ContentSubscriber).filter(ContentSubscriber.email == "reader@example.com").first()
        assert user is None

        site_user = session.query(SiteUser).filter(SiteUser.email == "diary-reader@example.com").first()
        assert site_user is not None
        session.add(
            ContentSubscriber(
                email="reader@example.com",
                initiator_site_user_id=site_user.id,
                content_types=["diary", "posts"],
                is_active=True,
            )
        )
        session.commit()

    revoke_response = client.patch(
        f"/api/v1/admin/moderation/diary-access-requests/{item['id']}",
        json={"revoke_access": True},
        headers=admin_headers,
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["has_access"] is False

    with get_session_factory()() as session:
        subscriber = session.query(ContentSubscriber).filter(ContentSubscriber.email == "reader@example.com").first()
        assert subscriber is not None
        assert subscriber.is_active is True
        assert subscriber.content_types == ["posts"]

    forbidden_detail = client.get(DIARY_DETAIL_PATH)
    assert forbidden_detail.status_code == 403


def test_disabling_diary_private_restores_public_detail_access(client) -> None:
    _set_diary_private_enabled(False)

    response = client.get(DIARY_DETAIL_PATH)

    assert response.status_code == 200
    assert response.json()["slug"] == DIARY_SLUG


def test_private_diary_machine_readable_surfaces_do_not_expose_details(client) -> None:
    llms = client.get("/llms.txt")
    feed = client.get("/feeds/diary.xml")
    search = client.get("/api/v1/site/search?q=春分")
    calendar = client.get("/api/v1/site/calendar?from=2026-03-01&to=2026-03-31")
    collection_html = client.get("/diary")
    detail_html = client.get(f"/diary/{DIARY_SLUG}")

    assert llms.status_code == 200
    assert "Do not access /diary or /diary/*" in llms.text
    assert "/feeds/diary.xml" not in llms.text
    assert "/api/v1/site/diary" not in llms.text

    assert feed.status_code == 200
    assert DIARY_SLUG not in feed.text

    assert search.status_code == 200
    assert all(item["type"] != "diary" for item in search.json()["items"])

    assert calendar.status_code == 200
    assert any(item["type"] == "diary" for item in calendar.json()["events"])

    assert collection_html.status_code == 200
    assert DIARY_SLUG not in collection_html.text
    assert "春分，天气转暖" not in collection_html.text

    assert detail_html.status_code == 200
    assert DIARY_SLUG not in detail_html.text
    assert "春分，天气转暖" not in detail_html.text
