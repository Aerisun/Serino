from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from aerisun.domain.automation.events import emit_comment_pending
from aerisun.domain.automation.schemas import WebhookSubscriptionCreate
from aerisun.domain.automation.service import create_webhook_subscription, dispatch_due_webhooks
from aerisun.domain.outbound_proxy.schemas import OutboundProxyConfigUpdate
from aerisun.domain.outbound_proxy.service import update_outbound_proxy_config


class FakeResponse:
    status_code = 200
    text = "ok"


def test_dispatch_due_webhooks_formats_feishu_payload(seeded_session, monkeypatch) -> None:
    create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Feishu alerts",
            target_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123",
            secret="feishu-secret",
            event_types=["comment.pending"],
        ),
    )

    emit_comment_pending(
        seeded_session,
        comment_id="comment-feishu-1",
        content_type="posts",
        content_slug="hello-world",
        author_name="Rowan",
        body_preview="A pending comment body.",
    )

    calls: list[dict[str, object]] = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    processed = dispatch_due_webhooks(seeded_session)

    assert processed == 1
    assert len(calls) == 1
    parsed = urlparse(str(calls[0]["url"]))
    query = parse_qs(parsed.query)
    assert "timestamp" in query
    assert "sign" in query
    payload = calls[0]["json"]
    assert payload["msg_type"] == "text"
    assert "comment.pending" in payload["content"]["text"]
    assert "comment-feishu-1" in payload["content"]["text"]


def test_dispatch_due_webhooks_formats_telegram_payload(seeded_session, monkeypatch) -> None:
    create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Telegram alerts",
            target_url="https://api.telegram.org/bot123:ABC/sendMessage?chat_id=987654321",
            event_types=["comment.pending"],
        ),
    )

    emit_comment_pending(
        seeded_session,
        comment_id="comment-telegram-1",
        content_type="posts",
        content_slug="hello-world",
        author_name="Rowan",
        body_preview="Another pending comment body.",
    )

    calls: list[dict[str, object]] = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    processed = dispatch_due_webhooks(seeded_session)

    assert processed == 1
    assert len(calls) == 1
    payload = calls[0]["json"]
    assert payload["chat_id"] == "987654321"
    assert payload["text"].startswith("Aerisun automation event")
    assert "Target: comment:comment-telegram-1" in payload["text"]


def test_webhook_test_endpoint_formats_feishu_request(client, admin_headers, monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        text = "ok"

    calls: list[dict[str, object]] = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    response = client.post(
        "/api/v1/admin/automation/webhooks/test",
        headers=admin_headers,
        json={
            "name": "Feishu alerts",
            "target_url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc123",
            "secret": "feishu-secret",
            "event_types": ["comment.pending"],
            "timeout_seconds": 10,
            "max_attempts": 6,
            "status": "active",
            "headers": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "feishu"
    assert len(calls) == 1
    parsed = urlparse(str(calls[0]["url"]))
    query = parse_qs(parsed.query)
    assert "timestamp" in query
    assert "sign" in query
    body = calls[0]["json"]
    assert body["msg_type"] == "text"
    assert "Aerisun webhook test" in body["content"]["text"]


def test_webhook_test_endpoint_formats_telegram_request(client, admin_headers, monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        text = "ok"

    calls: list[dict[str, object]] = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    response = client.post(
        "/api/v1/admin/automation/webhooks/test",
        headers=admin_headers,
        json={
            "name": "Telegram alerts",
            "target_url": "https://api.telegram.org/bot123:ABC/sendMessage?chat_id=987654321",
            "event_types": ["comment.pending"],
            "timeout_seconds": 10,
            "max_attempts": 6,
            "status": "active",
            "headers": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "telegram"
    assert len(calls) == 1
    body = calls[0]["json"]
    assert body["chat_id"] == "987654321"
    assert body["text"].startswith("Aerisun automation event")


def test_webhook_test_endpoint_uses_configured_proxy(client, admin_headers, monkeypatch) -> None:
    update_response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={"proxy_port": 7890, "webhook_enabled": True},
    )
    assert update_response.status_code == 200

    calls: list[dict[str, object]] = []

    def fake_post(url, json, headers, timeout, proxy=None, trust_env=True):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
                "proxy": proxy,
                "trust_env": trust_env,
            }
        )
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    response = client.post(
        "/api/v1/admin/automation/webhooks/test",
        headers=admin_headers,
        json={
            "name": "Proxy hook",
            "target_url": "https://example.com/webhook",
            "event_types": ["comment.pending"],
            "timeout_seconds": 10,
            "max_attempts": 6,
            "status": "active",
            "headers": {},
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(calls) == 1
    assert calls[0]["proxy"] == "http://127.0.0.1:7890"
    assert calls[0]["trust_env"] is False


def test_webhook_test_endpoint_persists_subscription_test_status(
    client,
    admin_headers,
    seeded_session,
    monkeypatch,
) -> None:
    subscription = create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Persisted status hook",
            target_url="https://api.telegram.org/bot123:ABC/sendMessage?chat_id=987654321",
            event_types=["comment.pending"],
            status="active",
        ),
    )

    class FailedResponse:
        status_code = 404
        text = "not found"

    monkeypatch.setattr(
        "aerisun.domain.automation.webhooks.httpx.post",
        lambda *args, **kwargs: FailedResponse(),
    )

    failed = client.post(
        f"/api/v1/admin/automation/webhooks/test?subscription_id={subscription.id}",
        headers=admin_headers,
        json={
            "name": "Persisted status hook",
            "target_url": "https://api.telegram.org/bot123:ABC/sendMessage?chat_id=987654321",
            "event_types": ["comment.pending"],
            "timeout_seconds": 10,
            "max_attempts": 6,
            "status": "active",
            "headers": {},
        },
    )

    assert failed.status_code == 200
    assert failed.json()["ok"] is False

    first_list = client.get("/api/v1/admin/automation/webhooks", headers=admin_headers)
    assert first_list.status_code == 200
    first_row = next(item for item in first_list.json() if item["id"] == subscription.id)
    assert first_row["last_test_status"] == "failed"
    assert first_row["last_test_error"] == "Webhook returned HTTP 404"
    assert first_row["last_tested_at"] is not None

    class SuccessResponse:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        "aerisun.domain.automation.webhooks.httpx.post",
        lambda *args, **kwargs: SuccessResponse(),
    )

    succeeded = client.post(
        f"/api/v1/admin/automation/webhooks/test?subscription_id={subscription.id}",
        headers=admin_headers,
        json={
            "name": "Persisted status hook",
            "target_url": "https://api.telegram.org/bot123:ABC/sendMessage?chat_id=987654321",
            "event_types": ["comment.pending"],
            "timeout_seconds": 10,
            "max_attempts": 6,
            "status": "active",
            "headers": {},
        },
    )

    assert succeeded.status_code == 200
    assert succeeded.json()["ok"] is True

    second_list = client.get("/api/v1/admin/automation/webhooks", headers=admin_headers)
    assert second_list.status_code == 200
    second_row = next(item for item in second_list.json() if item["id"] == subscription.id)
    assert second_row["last_test_status"] == "succeeded"
    assert second_row["last_test_error"] is None
    assert second_row["last_tested_at"] is not None


def test_webhook_telegram_connect_endpoint_detects_chat_and_sends_verification(
    client, admin_headers, monkeypatch
) -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object], text: str = "ok") -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = text

        def json(self) -> dict[str, object]:
            return self._payload

    get_calls: list[dict[str, object]] = []
    post_calls: list[dict[str, object]] = []

    def fake_get(url, params=None, timeout=None):
        get_calls.append({"url": url, "params": params, "timeout": timeout})
        if str(url).endswith("/getMe"):
            return FakeResponse(200, {"ok": True, "result": {"username": "Aerisun_webbot"}})
        if str(url).endswith("/deleteWebhook"):
            return FakeResponse(200, {"ok": True, "result": True})
        if str(url).endswith("/getUpdates"):
            return FakeResponse(
                200,
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 1001,
                            "message": {
                                "chat": {"id": 123456789},
                            },
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected get url: {url}")

    def fake_post(url, json, headers=None, timeout=None):
        post_calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse(200, {"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.get", fake_get)
    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    response = client.post(
        "/api/v1/admin/automation/webhooks/telegram/connect",
        headers=admin_headers,
        json={
            "bot_token": "123456:ABCDEF123456",
            "send_test_message": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "connected"
    assert payload["chat_id"] == 123456789
    assert payload["bot_username"] == "Aerisun_webbot"
    assert payload["target_url"].endswith("/sendMessage?chat_id=123456789")
    assert len(get_calls) == 3
    assert get_calls[2]["params"] == {"offset": -1, "limit": 1, "timeout": 0}
    assert len(post_calls) == 1
    assert post_calls[0]["json"]["chat_id"] == 123456789


def test_webhook_telegram_connect_endpoint_uses_configured_proxy(client, admin_headers, monkeypatch) -> None:
    update_response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={"proxy_port": 7890, "webhook_enabled": True},
    )
    assert update_response.status_code == 200

    calls: list[dict[str, object]] = []

    class FakeTelegramResponse:
        def __init__(self, status_code: int, payload: dict[str, object], text: str = "ok") -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = text

        def json(self) -> dict[str, object]:
            return self._payload

    def fake_get(url, *, params=None, timeout=None, proxy=None, trust_env=True):
        calls.append(
            {
                "method": "GET",
                "url": url,
                "params": params,
                "proxy": proxy,
                "trust_env": trust_env,
            }
        )
        if str(url).endswith("/getMe"):
            return FakeTelegramResponse(200, {"ok": True, "result": {"username": "aerisun_bot"}})
        if str(url).endswith("/deleteWebhook"):
            return FakeTelegramResponse(200, {"ok": True, "result": True})
        if str(url).endswith("/getUpdates"):
            return FakeTelegramResponse(200, {"ok": True, "result": []})
        raise AssertionError(f"Unexpected Telegram URL: {url}")

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.get", fake_get)

    response = client.post(
        "/api/v1/admin/automation/webhooks/telegram/connect",
        headers=admin_headers,
        json={
            "bot_token": "123456:ABCDEF1234567890",
            "send_test_message": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "awaiting_message"
    assert calls
    assert all(call["proxy"] == "http://127.0.0.1:7890" for call in calls)
    assert all(call["trust_env"] is False for call in calls)


def test_webhook_telegram_connect_endpoint_returns_awaiting_message_when_no_updates(
    client, admin_headers, monkeypatch
) -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object], text: str = "ok") -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = text

        def json(self) -> dict[str, object]:
            return self._payload

    post_calls: list[dict[str, object]] = []

    get_calls: list[dict[str, object]] = []

    def fake_get(url, params=None, timeout=None):
        get_calls.append({"url": url, "params": params, "timeout": timeout})
        if str(url).endswith("/getMe"):
            return FakeResponse(200, {"ok": True, "result": {"username": "Aerisun_webbot"}})
        if str(url).endswith("/deleteWebhook"):
            return FakeResponse(200, {"ok": True, "result": True})
        if str(url).endswith("/getUpdates"):
            return FakeResponse(200, {"ok": True, "result": []})
        raise AssertionError(f"unexpected get url: {url}")

    def fake_post(url, json, headers=None, timeout=None):
        post_calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse(200, {"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.get", fake_get)
    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    response = client.post(
        "/api/v1/admin/automation/webhooks/telegram/connect",
        headers=admin_headers,
        json={
            "bot_token": "123456:ABCDEF123456",
            "send_test_message": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "awaiting_message"
    assert len(get_calls) == 4
    assert get_calls[2]["params"] == {"offset": -1, "limit": 1, "timeout": 0}
    assert get_calls[3]["params"] == {"limit": 1, "timeout": 8}
    assert post_calls == []


def test_webhook_telegram_connect_endpoint_retries_after_tls_timeout(client, admin_headers, monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object], text: str = "ok") -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = text

        def json(self) -> dict[str, object]:
            return self._payload

    get_calls: list[dict[str, object]] = []
    me_attempts = {"count": 0}

    def fake_get(url, params=None, timeout=None):
        get_calls.append({"url": url, "params": params, "timeout": timeout})
        if str(url).endswith("/getMe"):
            me_attempts["count"] += 1
            if me_attempts["count"] == 1:
                raise httpx.ConnectTimeout("_ssl.c:1015: The handshake operation timed out")
            return FakeResponse(200, {"ok": True, "result": {"username": "Aerisun_webbot"}})
        if str(url).endswith("/deleteWebhook"):
            return FakeResponse(200, {"ok": True, "result": True})
        if str(url).endswith("/getUpdates"):
            return FakeResponse(
                200,
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 2002,
                            "message": {
                                "chat": {"id": 987654321},
                            },
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected get url: {url}")

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.get", fake_get)

    response = client.post(
        "/api/v1/admin/automation/webhooks/telegram/connect",
        headers=admin_headers,
        json={
            "bot_token": "123456:ABCDEF123456",
            "send_test_message": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "connected"
    assert payload["chat_id"] == 987654321
    assert me_attempts["count"] == 2
    assert sum(1 for call in get_calls if str(call["url"]).endswith("/getMe")) == 2


def test_dispatch_due_webhooks_uses_configured_proxy(seeded_session, monkeypatch) -> None:
    update_outbound_proxy_config(
        seeded_session,
        OutboundProxyConfigUpdate(proxy_port=7890, webhook_enabled=True),
    )
    create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Proxy delivery",
            target_url="https://example.com/webhook",
            event_types=["comment.pending"],
        ),
    )

    emit_comment_pending(
        seeded_session,
        comment_id="comment-proxy-1",
        content_type="posts",
        content_slug="hello-world",
        author_name="Rowan",
        body_preview="Proxy delivery body.",
    )

    calls: list[dict[str, object]] = []

    def fake_post(url, json, headers, timeout, proxy=None, trust_env=True):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
                "proxy": proxy,
                "trust_env": trust_env,
            }
        )
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    processed = dispatch_due_webhooks(seeded_session)

    assert processed == 1
    assert len(calls) == 1
    assert calls[0]["proxy"] == "http://127.0.0.1:7890"
    assert calls[0]["trust_env"] is False
