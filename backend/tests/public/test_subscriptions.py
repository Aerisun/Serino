from __future__ import annotations

from datetime import timedelta

from aerisun.core.db import get_session_factory
from aerisun.core.time import shanghai_now
from aerisun.domain.diary_access.models import DiaryAccessRequest
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.site_auth.models import SiteAdminIdentity, SiteUser
from aerisun.domain.site_config.models import SiteProfile
from aerisun.domain.subscription.models import ContentNotification, ContentSubscriber
from aerisun.domain.subscription.service import get_subscription_config_orm

PUBLIC_BASE = "/api/v1/site"


def _enable_subscriptions() -> None:
    with get_session_factory()() as session:
        config = get_subscription_config_orm(session)
        config.enabled = True
        config.smtp_test_passed = True
        config.smtp_host = "smtp.example.com"
        config.smtp_port = 587
        config.smtp_from_email = "no-reply@example.com"
        config.smtp_from_name = "Aerisun Bot"
        config.smtp_use_tls = False
        config.smtp_use_ssl = False
        session.commit()


def _login_site_user(client, *, email: str) -> None:
    response = client.post(
        "/api/v1/site-auth/email",
        json={
            "email": email,
            "display_name": "Subscriber",
            "avatar_url": "/api/v1/avatars/10.x/notionists/svg?seed=subscriber",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["requires_profile"] is False


def _grant_diary_access(email: str) -> None:
    with get_session_factory()() as session:
        user = session.query(SiteUser).filter(SiteUser.email == email).first()
        assert user is not None
        now = shanghai_now()
        session.add(
            DiaryAccessRequest(
                site_user_id=user.id,
                reason="测试授权",
                status="approved",
                granted_at=now,
                reviewed_at=now,
                expires_at=now + timedelta(days=7),
            )
        )
        session.commit()


def test_site_config_exposes_public_subscription_flag(client) -> None:
    response = client.get(f"{PUBLIC_BASE}/site")

    assert response.status_code == 200
    assert response.json()["site"]["feature_flags"]["content_subscription"] is False

    _enable_subscriptions()

    enabled_response = client.get(f"{PUBLIC_BASE}/site")

    assert enabled_response.status_code == 200
    assert enabled_response.json()["site"]["feature_flags"]["content_subscription"] is True


def test_public_subscription_requires_enabled(client) -> None:
    response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["posts", "thoughts"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "订阅功能尚未开启"


def test_public_subscription_creates_and_updates_subscriber(client, monkeypatch) -> None:
    _enable_subscriptions()
    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", lambda **_: None)

    create_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["posts", "thoughts"]},
    )

    assert create_response.status_code == 201
    assert create_response.json() == {
        "email": "reader@example.com",
        "content_types": ["posts", "thoughts"],
        "subscribed": True,
    }

    update_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "Reader@Example.com", "content_types": ["posts", "excerpts"]},
    )

    assert update_response.status_code == 201
    assert update_response.json() == {
        "email": "reader@example.com",
        "content_types": ["excerpts", "posts"],
        "subscribed": True,
    }

    with get_session_factory()() as session:
        subscribers = session.query(ContentSubscriber).all()

    assert len(subscribers) == 1
    assert subscribers[0].email == "reader@example.com"
    assert subscribers[0].content_types == ["excerpts", "posts"]


def test_private_diary_subscription_requires_active_access(client, monkeypatch) -> None:
    _enable_subscriptions()
    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", lambda **_: None)

    anonymous_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["diary"]},
    )
    assert anonymous_response.status_code == 422
    assert anonymous_response.json()["detail"] == "日记订阅需要先登录并获得查看权限。"

    _login_site_user(client, email="reader@example.com")
    forbidden_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["diary"]},
    )
    assert forbidden_response.status_code == 422
    assert forbidden_response.json()["detail"] == "日记订阅需要先登录并获得查看权限。"

    _grant_diary_access("reader@example.com")
    allowed_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["diary", "posts"]},
    )
    assert allowed_response.status_code == 201
    assert allowed_response.json()["content_types"] == ["diary", "posts"]

    with get_session_factory()() as session:
        user = session.query(SiteUser).filter(SiteUser.email == "reader@example.com").first()
        assert user is not None
        access = (
            session.query(DiaryAccessRequest)
            .filter(DiaryAccessRequest.site_user_id == user.id)
            .order_by(DiaryAccessRequest.created_at.desc())
            .first()
        )
        assert access is not None
        access.expires_at = shanghai_now() - timedelta(seconds=1)
        session.commit()

    status_response = client.get(f"{PUBLIC_BASE}/subscriptions/me")
    assert status_response.status_code == 200
    assert status_response.json() == {
        "email": "reader@example.com",
        "content_types": ["posts"],
        "subscribed": True,
    }
    with get_session_factory()() as session:
        subscriber = session.query(ContentSubscriber).filter(ContentSubscriber.email == "reader@example.com").first()
        assert subscriber is not None
        assert subscriber.is_active is True
        assert subscriber.content_types == ["posts"]


def test_private_diary_notification_rechecks_subscriber_access(seeded_session) -> None:
    profile = seeded_session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
    assert profile is not None
    profile.feature_flags = {
        **dict(profile.feature_flags or {}),
        "diary_private_enabled": True,
    }
    config = get_subscription_config_orm(seeded_session)
    config.enabled = True
    config.smtp_test_passed = True
    config.allowed_content_types = ["diary"]

    authorized = SiteUser(email="authorized@example.com", display_name="Authorized", avatar_url="")
    unauthorized = SiteUser(email="unauthorized@example.com", display_name="Unauthorized", avatar_url="")
    admin_site_user = SiteUser(email="admin-delivery@example.com", display_name="Admin", avatar_url="")
    admin_user = AdminUser(username="diary-delivery-admin", password_hash="test")
    seeded_session.add_all([authorized, unauthorized, admin_site_user, admin_user])
    seeded_session.flush()
    now = shanghai_now()
    seeded_session.add(
        DiaryAccessRequest(
            site_user_id=authorized.id,
            reason="测试授权",
            status="approved",
            granted_at=now,
            reviewed_at=now,
            expires_at=now + timedelta(days=7),
        )
    )
    seeded_session.add(
        SiteAdminIdentity(
            site_user_id=admin_site_user.id,
            admin_user_id=admin_user.id,
            provider="email",
            identifier="admin-delivery@example.com",
            email="admin-delivery@example.com",
        )
    )
    seeded_session.add_all(
        [
            ContentSubscriber(
                email="admin-delivery@example.com",
                initiator_site_user_id=admin_site_user.id,
                content_types=["diary"],
                is_active=True,
            ),
            ContentSubscriber(
                email="authorized-delivery@example.com",
                initiator_site_user_id=authorized.id,
                content_types=["diary"],
                is_active=True,
            ),
            ContentSubscriber(
                email="unauthorized-delivery@example.com",
                initiator_site_user_id=unauthorized.id,
                content_types=["diary"],
                is_active=True,
            ),
            ContentSubscriber(
                email="anonymous-delivery@example.com",
                content_types=["diary"],
                is_active=True,
            ),
        ]
    )
    seeded_session.add(
        ContentNotification(
            content_type="diary",
            content_slug="private-day",
            content_title="Private Day",
            content_summary="Private summary",
            content_url="https://example.com/diary/private-day",
            published_at=now,
        )
    )
    seeded_session.commit()

    from aerisun.domain.subscription.service import _recipient_emails_for_notification

    assert _recipient_emails_for_notification(seeded_session, config=config, content_type="diary") == [
        "admin-delivery@example.com",
        "authorized-delivery@example.com",
    ]
    admin_subscriber = (
        seeded_session.query(ContentSubscriber).filter(ContentSubscriber.email == "admin-delivery@example.com").first()
    )
    authorized_subscriber = (
        seeded_session.query(ContentSubscriber)
        .filter(ContentSubscriber.email == "authorized-delivery@example.com")
        .first()
    )
    unauthorized_subscriber = (
        seeded_session.query(ContentSubscriber)
        .filter(ContentSubscriber.email == "unauthorized-delivery@example.com")
        .first()
    )
    anonymous_subscriber = (
        seeded_session.query(ContentSubscriber)
        .filter(ContentSubscriber.email == "anonymous-delivery@example.com")
        .first()
    )
    assert admin_subscriber is not None
    assert authorized_subscriber is not None
    assert unauthorized_subscriber is not None
    assert anonymous_subscriber is not None
    assert admin_subscriber.content_types == ["diary"]
    assert authorized_subscriber.content_types == ["diary"]
    assert unauthorized_subscriber.content_types == []
    assert unauthorized_subscriber.is_active is False
    assert anonymous_subscriber.content_types == ["diary"]


def test_public_subscription_respects_admin_allowed_content_types(client) -> None:
    with get_session_factory()() as session:
        config = get_subscription_config_orm(session)
        config.enabled = True
        config.smtp_test_passed = True
        config.allowed_content_types = ["posts"]
        session.commit()

    response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["diary"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "以下订阅类型暂未开放：diary"


def test_public_subscription_fails_when_welcome_email_send_fails(client, monkeypatch) -> None:
    _enable_subscriptions()

    def _raise_send_error(**_: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", _raise_send_error)

    response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["posts", "thoughts"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "订阅确认邮件发送失败，请确认邮箱地址后重试"

    with get_session_factory()() as session:
        subscribers = session.query(ContentSubscriber).all()
    assert subscribers == []


def test_public_subscription_me_requires_login(client) -> None:
    response = client.get(f"{PUBLIC_BASE}/subscriptions/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "请先登录。"


def test_public_subscription_status_and_unsubscribe_by_email(client, monkeypatch) -> None:
    _enable_subscriptions()
    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", lambda **_: None)

    create_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["posts", "thoughts"]},
    )
    assert create_response.status_code == 201

    status_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/status",
        json={"email": "Reader@Example.com"},
    )
    assert status_response.status_code == 200
    assert status_response.json() == {
        "email": "reader@example.com",
        "content_types": ["posts", "thoughts"],
        "subscribed": True,
    }

    unsubscribe_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/unsubscribe",
        json={"email": "Reader@Example.com"},
    )
    assert unsubscribe_response.status_code == 200
    assert unsubscribe_response.json() == {
        "email": "reader@example.com",
        "unsubscribed": True,
    }

    status_after_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/status",
        json={"email": "reader@example.com"},
    )
    assert status_after_response.status_code == 200
    assert status_after_response.json() == {
        "email": "reader@example.com",
        "content_types": ["posts", "thoughts"],
        "subscribed": False,
    }


def test_public_subscription_me_status_and_unsubscribe(client, monkeypatch) -> None:
    _enable_subscriptions()
    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", lambda **_: None)
    _login_site_user(client, email="reader@example.com")

    create_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "reader@example.com", "content_types": ["posts", "thoughts"]},
    )
    assert create_response.status_code == 201

    status_response = client.get(f"{PUBLIC_BASE}/subscriptions/me")
    assert status_response.status_code == 200
    assert status_response.json() == {
        "email": "reader@example.com",
        "content_types": ["posts", "thoughts"],
        "subscribed": True,
    }

    unsubscribe_response = client.delete(f"{PUBLIC_BASE}/subscriptions/me")
    assert unsubscribe_response.status_code == 200
    assert unsubscribe_response.json() == {
        "email": "reader@example.com",
        "unsubscribed": True,
    }

    status_after_response = client.get(f"{PUBLIC_BASE}/subscriptions/me")
    assert status_after_response.status_code == 200
    assert status_after_response.json() == {
        "email": "reader@example.com",
        "content_types": ["posts", "thoughts"],
        "subscribed": False,
    }


def test_public_subscription_stores_initiating_visitor_independently_from_subscription_email(
    client, monkeypatch
) -> None:
    _enable_subscriptions()
    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", lambda **_: None)
    _login_site_user(client, email="visitor@example.com")

    response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "delivery@example.com", "content_types": ["posts"]},
    )

    assert response.status_code == 201

    with get_session_factory()() as session:
        subscriber = session.query(ContentSubscriber).filter(ContentSubscriber.email == "delivery@example.com").first()
        visitor = session.query(SiteUser).filter(SiteUser.email == "visitor@example.com").first()

    assert subscriber is not None
    assert visitor is not None
    assert subscriber.initiator_site_user_id == visitor.id


def test_my_subscription_list_only_returns_current_visitors_initiated_emails(client, monkeypatch) -> None:
    _enable_subscriptions()
    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", lambda **_: None)

    _login_site_user(client, email="visitor-a@example.com")
    first_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "visitor-a-delivery@example.com", "content_types": ["posts", "thoughts"]},
    )
    assert first_response.status_code == 201

    client.post("/api/v1/site-auth/logout")
    _login_site_user(client, email="visitor-b@example.com")
    second_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "visitor-b-delivery@example.com", "content_types": ["excerpts"]},
    )
    assert second_response.status_code == 201

    visitor_b_list = client.get(f"{PUBLIC_BASE}/subscriptions/mine")
    assert visitor_b_list.status_code == 200
    assert visitor_b_list.json() == [
        {
            "email": "visitor-b-delivery@example.com",
            "content_types": ["excerpts"],
            "subscribed": True,
        }
    ]

    client.post("/api/v1/site-auth/logout")
    _login_site_user(client, email="visitor-a@example.com")
    visitor_a_list = client.get(f"{PUBLIC_BASE}/subscriptions/mine")
    assert visitor_a_list.status_code == 200
    assert visitor_a_list.json() == [
        {
            "email": "visitor-a-delivery@example.com",
            "content_types": ["posts", "thoughts"],
            "subscribed": True,
        }
    ]


def test_my_subscription_unsubscribe_only_affects_current_visitors_initiated_email(client, monkeypatch) -> None:
    _enable_subscriptions()
    monkeypatch.setattr("aerisun.domain.subscription.service._send_email", lambda **_: None)

    _login_site_user(client, email="visitor-a@example.com")
    first_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "visitor-a-delivery@example.com", "content_types": ["posts"]},
    )
    assert first_response.status_code == 201

    client.post("/api/v1/site-auth/logout")
    _login_site_user(client, email="visitor-b@example.com")
    second_response = client.post(
        f"{PUBLIC_BASE}/subscriptions/",
        json={"email": "visitor-b-delivery@example.com", "content_types": ["thoughts"]},
    )
    assert second_response.status_code == 201

    forbidden_unsubscribe = client.post(
        f"{PUBLIC_BASE}/subscriptions/mine/unsubscribe",
        json={"email": "visitor-a-delivery@example.com"},
    )
    assert forbidden_unsubscribe.status_code == 200
    assert forbidden_unsubscribe.json() == {
        "email": "visitor-a-delivery@example.com",
        "unsubscribed": True,
    }

    visitor_b_list = client.get(f"{PUBLIC_BASE}/subscriptions/mine")
    assert visitor_b_list.status_code == 200
    assert visitor_b_list.json() == [
        {
            "email": "visitor-b-delivery@example.com",
            "content_types": ["thoughts"],
            "subscribed": True,
        }
    ]

    client.post("/api/v1/site-auth/logout")
    _login_site_user(client, email="visitor-a@example.com")
    visitor_a_list = client.get(f"{PUBLIC_BASE}/subscriptions/mine")
    assert visitor_a_list.status_code == 200
    assert visitor_a_list.json() == [
        {
            "email": "visitor-a-delivery@example.com",
            "content_types": ["posts"],
            "subscribed": True,
        }
    ]
