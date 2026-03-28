from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.domain.subscription.models import ContentSubscriber
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
            "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=subscriber",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["requires_profile"] is False


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
        json={"email": "Reader@Example.com", "content_types": ["diary", "excerpts"]},
    )

    assert update_response.status_code == 201
    assert update_response.json() == {
        "email": "reader@example.com",
        "content_types": ["diary", "excerpts"],
        "subscribed": True,
    }

    with get_session_factory()() as session:
        subscribers = session.query(ContentSubscriber).all()

    assert len(subscribers) == 1
    assert subscribers[0].email == "reader@example.com"
    assert subscribers[0].content_types == ["diary", "excerpts"]


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
