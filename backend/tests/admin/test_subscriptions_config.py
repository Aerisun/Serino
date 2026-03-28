from __future__ import annotations

from typing import ClassVar

import httpx
import respx

from aerisun.core.base import utcnow
from aerisun.domain.subscription.models import ContentNotification, ContentSubscriber
from aerisun.domain.subscription.service import (
    MICROSOFT_SMTP_SCOPE,
    dispatch_content_subscription_notifications,
    get_subscription_config_orm,
)

ADMIN_BASE = "/api/v1/admin/subscriptions"


def test_admin_subscription_config_roundtrip(client, admin_headers) -> None:
    response = client.get(f"{ADMIN_BASE}/config", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["subscriber_count"] == 0

    update_response = client.put(
        f"{ADMIN_BASE}/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "smtp_auth_mode": "password",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "mailer",
            "smtp_password": "secret",
            "smtp_oauth_tenant": "common",
            "smtp_oauth_client_id": "",
            "smtp_oauth_client_secret": "",
            "smtp_oauth_refresh_token": "",
            "smtp_from_email": "no-reply@example.com",
            "smtp_from_name": "Aerisun Bot",
            "smtp_reply_to": "hello@example.com",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["enabled"] is True
    assert payload["smtp_auth_mode"] == "password"
    assert payload["smtp_host"] == "smtp.example.com"
    assert payload["smtp_from_email"] == "no-reply@example.com"
    assert payload["smtp_use_tls"] is True
    assert payload["smtp_use_ssl"] is False


def test_dispatch_content_subscription_notifications_sends_matching_emails(seeded_session, monkeypatch) -> None:
    config = get_subscription_config_orm(seeded_session)
    config.enabled = True
    config.smtp_host = "smtp.example.com"
    config.smtp_port = 587
    config.smtp_username = "mailer"
    config.smtp_password = "secret"
    config.smtp_from_email = "no-reply@example.com"
    config.smtp_from_name = "Aerisun Bot"
    config.smtp_reply_to = "hello@example.com"
    config.smtp_use_tls = True
    config.smtp_use_ssl = False

    subscriber = ContentSubscriber(
        email="reader@example.com",
        content_types=["posts"],
        is_active=True,
    )
    seeded_session.add(subscriber)

    notification = ContentNotification(
        content_type="posts",
        content_slug="subscription-test-post",
        content_title="Subscription Test Post",
        content_summary="A new post is ready.",
        content_url="https://example.com/posts/subscription-test-post",
        published_at=utcnow(),
    )
    seeded_session.add(notification)
    seeded_session.commit()

    class FakeSMTP:
        messages: ClassVar[list] = []

        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout
            self.started_tls = False
            self.logged_in = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            self.started_tls = True

        def ehlo(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            self.logged_in = (username, password)

        def send_message(self, message) -> None:
            FakeSMTP.messages.append(message)

    monkeypatch.setattr("aerisun.domain.subscription.service.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("aerisun.domain.subscription.service._ensure_notification_records", lambda session, site_url: 0)

    summary = dispatch_content_subscription_notifications()

    assert summary == {"created": 0, "sent": 1, "skipped": 0}
    assert len(FakeSMTP.messages) == 1
    message = FakeSMTP.messages[0]
    assert message["Subject"] == "[Aerisun] Subscription Test Post"
    assert message["Bcc"] == "reader@example.com"
    assert "https://example.com/posts/subscription-test-post" in message.get_content()

    seeded_session.refresh(notification)
    assert notification.delivered_at is not None


def test_admin_subscription_config_test_email_uses_payload_settings(client, admin_headers, monkeypatch) -> None:
    class FakeSMTP:
        messages: ClassVar[list] = []

        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            self.logged_in = (username, password)

        def send_message(self, message) -> None:
            FakeSMTP.messages.append(message)

    monkeypatch.setattr("aerisun.domain.subscription.service.smtplib.SMTP", FakeSMTP)

    response = client.post(
        f"{ADMIN_BASE}/config/test",
        headers=admin_headers,
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "mailer@example.com",
            "smtp_password": "secret",
            "smtp_from_email": "no-reply@example.com",
            "smtp_from_name": "Aerisun Bot",
            "smtp_reply_to": "hello@example.com",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"recipient": "do-not-reply@course.pku.edu.cn"}
    assert len(FakeSMTP.messages) == 1
    message = FakeSMTP.messages[0]
    assert message["To"] == "do-not-reply@course.pku.edu.cn"
    assert message["From"] == "Aerisun Bot <no-reply@example.com>"
    assert message["Subject"] == "[Aerisun] SMTP Test"


@respx.mock
def test_admin_subscription_config_test_email_supports_microsoft_oauth2(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    class FakeSMTP:
        messages: ClassVar[list] = []
        auth_commands: ClassVar[list[str]] = []

        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def starttls(self) -> None:
            return None

        def docmd(self, command: str, arguments: str):
            FakeSMTP.auth_commands.append(f"{command} {arguments}")
            return (235, b"2.7.0 Authentication successful")

        def send_message(self, message) -> None:
            FakeSMTP.messages.append(message)

    monkeypatch.setattr("aerisun.domain.subscription.service.smtplib.SMTP", FakeSMTP)
    respx.post("https://login.microsoftonline.com/consumers/oauth2/v2.0/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "microsoft-access-token",
                "refresh_token": "updated-refresh-token",
                "scope": MICROSOFT_SMTP_SCOPE,
                "token_type": "Bearer",
            },
        )
    )

    response = client.post(
        f"{ADMIN_BASE}/config/test",
        headers=admin_headers,
        json={
            "smtp_auth_mode": "microsoft_oauth2",
            "smtp_host": "smtp-mail.outlook.com",
            "smtp_port": 587,
            "smtp_username": "rowan@example.com",
            "smtp_oauth_tenant": "consumers",
            "smtp_oauth_client_id": "client-id",
            "smtp_oauth_client_secret": "client-secret",
            "smtp_oauth_refresh_token": "refresh-token",
            "smtp_from_email": "rowan@example.com",
            "smtp_from_name": "Aerisun Bot",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"recipient": "do-not-reply@course.pku.edu.cn"}
    assert len(FakeSMTP.messages) == 1
    assert len(FakeSMTP.auth_commands) == 1
    assert FakeSMTP.auth_commands[0].startswith("AUTH XOAUTH2 ")


def test_admin_subscription_config_test_email_returns_readable_error(client, admin_headers, monkeypatch) -> None:
    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            return None

        def send_message(self, message) -> None:
            raise OSError("connection refused")

    monkeypatch.setattr("aerisun.domain.subscription.service.smtplib.SMTP", FakeSMTP)

    response = client.post(
        f"{ADMIN_BASE}/config/test",
        headers=admin_headers,
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "mailer@example.com",
            "smtp_password": "secret",
            "smtp_from_email": "no-reply@example.com",
            "smtp_from_name": "Aerisun Bot",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "请检查 SMTP 主机、端口、用户名、密码和加密方式是否正确"


def test_admin_subscription_config_test_email_requires_minimum_fields(client, admin_headers) -> None:
    response = client.post(
        f"{ADMIN_BASE}/config/test",
        headers=admin_headers,
        json={
            "smtp_port": 587,
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "请先填写 SMTP 主机、端口和发件邮箱"


def test_admin_subscription_config_test_email_requires_microsoft_oauth2_fields(client, admin_headers) -> None:
    response = client.post(
        f"{ADMIN_BASE}/config/test",
        headers=admin_headers,
        json={
            "smtp_auth_mode": "microsoft_oauth2",
            "smtp_host": "smtp-mail.outlook.com",
            "smtp_port": 587,
            "smtp_from_email": "rowan@example.com",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "请先填写 SMTP 主机、端口、发件邮箱，以及 Microsoft OAuth2 的租户、Client ID、Client Secret 和 Refresh Token"
    )
