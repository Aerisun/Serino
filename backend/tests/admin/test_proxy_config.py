from __future__ import annotations

from contextlib import nullcontext


def test_admin_outbound_proxy_config_roundtrip(client, admin_headers) -> None:
    response = client.get("/api/v1/admin/proxy-config", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "proxy_port": None,
        "webhook_enabled": False,
    }

    update_response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={
            "proxy_port": 7890,
            "webhook_enabled": True,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "proxy_port": 7890,
        "webhook_enabled": True,
    }

    reload_response = client.get("/api/v1/admin/proxy-config", headers=admin_headers)
    assert reload_response.status_code == 200
    assert reload_response.json()["proxy_port"] == 7890
    assert reload_response.json()["webhook_enabled"] is True


def test_admin_outbound_proxy_config_rejects_enabling_webhook_without_port(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={"webhook_enabled": True},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "开启 Webhook 代理前，请先设置代理端口"


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
