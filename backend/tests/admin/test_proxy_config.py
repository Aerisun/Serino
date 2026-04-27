from __future__ import annotations

from contextlib import nullcontext

import httpx


def test_admin_outbound_proxy_config_roundtrip(client, admin_headers) -> None:
    response = client.get("/api/v1/admin/proxy-config", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "proxy_port": None,
        "webhook_enabled": False,
        "oauth_enabled": False,
    }

    update_response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={
            "proxy_port": 7890,
            "webhook_enabled": True,
            "oauth_enabled": True,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "proxy_port": 7890,
        "webhook_enabled": True,
        "oauth_enabled": True,
    }

    reload_response = client.get("/api/v1/admin/proxy-config", headers=admin_headers)
    assert reload_response.status_code == 200
    assert reload_response.json()["proxy_port"] == 7890
    assert reload_response.json()["webhook_enabled"] is True
    assert reload_response.json()["oauth_enabled"] is True


def test_admin_outbound_proxy_config_accepts_proxy_url_port(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={
            "proxy_port": "http://127.0.0.1:7890",
            "oauth_enabled": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["proxy_port"] == 7890
    assert response.json()["oauth_enabled"] is True


def test_admin_outbound_proxy_config_rejects_enabling_webhook_without_port(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={"webhook_enabled": True},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "开启 Webhook 代理前，请先设置代理端口"


def test_admin_outbound_proxy_config_rejects_enabling_oauth_without_port(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={"oauth_enabled": True},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "开启 OAuth 代理前，请先设置代理端口"


def test_enabling_google_login_does_not_require_oauth_proxy_scope(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/visitors/config",
        headers=admin_headers,
        json={
            "visitor_oauth_providers": ["google"],
        },
    )

    assert response.status_code == 200
    assert response.json()["visitor_oauth_providers"] == ["google"]


def test_admin_outbound_proxy_healthcheck_uses_local_proxy_port(client, admin_headers, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_connection(address, timeout):
        captured["address"] = address
        captured["timeout"] = timeout
        return nullcontext()

    class FakeResponse:
        status_code = 200

    def fake_get(url, *, proxy=None, timeout=None, follow_redirects=False, trust_env=True):
        captured["url"] = str(url)
        captured["proxy"] = proxy
        captured["follow_redirects"] = follow_redirects
        captured["trust_env"] = trust_env
        captured["http_timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.socket.create_connection", fake_create_connection)
    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.httpx.get", fake_get)

    response = client.post(
        "/api/v1/admin/proxy-config/test",
        headers=admin_headers,
        json={"proxy_port": 7890},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["proxy_url"] == "http://127.0.0.1:7890"
    assert payload["status_code"] == 200
    assert captured["address"] == ("127.0.0.1", 7890)
    assert captured["proxy"] == "http://127.0.0.1:7890"
    assert captured["trust_env"] is False


def test_admin_outbound_proxy_healthcheck_tries_host_gateway_when_localhost_unavailable(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {"addresses": []}

    def fake_create_connection(address, timeout):
        captured["addresses"].append(address)
        if address[0] == "127.0.0.1":
            raise OSError("connection refused")
        captured["timeout"] = timeout
        return nullcontext()

    class FakeResponse:
        status_code = 200

    def fake_get(url, *, proxy=None, timeout=None, follow_redirects=False, trust_env=True):
        captured["proxy"] = proxy
        captured["trust_env"] = trust_env
        return FakeResponse()

    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.socket.create_connection", fake_create_connection)
    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.httpx.get", fake_get)
    monkeypatch.setattr(
        "aerisun.domain.outbound_proxy.service._read_default_gateway_ip",
        lambda: "172.17.0.1",
    )

    response = client.post(
        "/api/v1/admin/proxy-config/test",
        headers=admin_headers,
        json={"proxy_port": 7890},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert ("127.0.0.1", 7890) in captured["addresses"]
    assert ("host.docker.internal", 7890) in captured["addresses"]
    assert payload["proxy_url"] == "http://host.docker.internal:7890"
    assert captured["proxy"] == "http://host.docker.internal:7890"


def test_send_outbound_request_prefers_reachable_host_gateway_proxy(seeded_session, monkeypatch) -> None:
    from aerisun.domain.outbound_proxy.schemas import OutboundProxyConfigUpdate
    from aerisun.domain.outbound_proxy.service import send_outbound_request, update_outbound_proxy_config

    update_outbound_proxy_config(
        seeded_session,
        OutboundProxyConfigUpdate(proxy_port=7890, oauth_enabled=True),
    )

    captured: dict[str, object] = {"addresses": []}

    def fake_create_connection(address, timeout):
        captured["addresses"].append(address)
        if address[0] == "127.0.0.1":
            raise OSError("connection refused")
        return nullcontext()

    def fake_request(method, url, *, proxy=None, trust_env=True, **kwargs):
        captured["proxy"] = proxy
        captured["trust_env"] = trust_env
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.socket.create_connection", fake_create_connection)
    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.httpx.request", fake_request)
    monkeypatch.setattr(
        "aerisun.domain.outbound_proxy.service._read_default_gateway_ip",
        lambda: "172.17.0.1",
    )

    response = send_outbound_request(
        seeded_session,
        scope="oauth",
        method="GET",
        url="https://example.com/oauth-check",
        timeout=5.0,
    )

    assert response.status_code == 200
    assert ("127.0.0.1", 7890) in captured["addresses"]
    assert ("host.docker.internal", 7890) in captured["addresses"]
    assert captured["proxy"] == "http://host.docker.internal:7890"
    assert captured["trust_env"] is False


def test_send_outbound_request_falls_back_to_environment_proxy(seeded_session, monkeypatch) -> None:
    from aerisun.domain.outbound_proxy.schemas import OutboundProxyConfigUpdate
    from aerisun.domain.outbound_proxy.service import send_outbound_request, update_outbound_proxy_config

    update_outbound_proxy_config(
        seeded_session,
        OutboundProxyConfigUpdate(proxy_port=7890, oauth_enabled=True),
    )

    def fake_create_connection(_address, _timeout):
        raise OSError("unreachable")

    def fake_request(method, url, *, proxy=None, trust_env=True, **kwargs):
        if trust_env:
            return httpx.Response(200, json={"via": "env"})
        raise httpx.ConnectError("configured proxy failed", request=httpx.Request(method, url))

    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.socket.create_connection", fake_create_connection)
    monkeypatch.setattr("aerisun.domain.outbound_proxy.service.httpx.request", fake_request)
    monkeypatch.setenv("HTTPS_PROXY", "http://system-proxy.local:7890")

    response = send_outbound_request(
        seeded_session,
        scope="oauth",
        method="GET",
        url="https://example.com/oauth-check",
        timeout=5.0,
    )

    assert response.status_code == 200
