from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError as PydanticValidationError

from aerisun.core.settings import get_settings
from aerisun.domain.service_forwards.schemas import ServiceForwardWrite
from aerisun.domain.service_forwards.service import render_route_file


def _route_id(slug: str) -> str:
    return hashlib.sha256(f"/{slug}".encode()).hexdigest()[:16]


def test_admin_can_create_and_list_local_service_forward(client, admin_headers) -> None:
    create_response = client.post(
        "/api/v1/admin/service-forwards",
        headers=admin_headers,
        json={
            "name": "Grafana",
            "slug": "grafana",
            "source": "local",
            "port": 3000,
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"] == _route_id("grafana")
    assert created["name"] == "Grafana"
    assert created["slug"] == "grafana"
    assert created["path"] == "/grafana"
    assert created["source"] == "local"
    assert created["target_url"] == "http://127.0.0.1:3000"
    assert created["public_url"].endswith("/grafana")
    assert created["status"] == "unchecked"

    list_response = client.get("/api/v1/admin/service-forwards", headers=admin_headers)

    assert list_response.status_code == 200
    assert list_response.json() == [created]


def test_admin_allows_parent_and_child_routes_with_child_dispatched_first(client, admin_headers) -> None:
    parent_response = client.post(
        "/api/v1/admin/service-forwards",
        headers=admin_headers,
        json={"name": "Model API", "slug": "model", "source": "local", "port": 8001},
    )
    child_response = client.post(
        "/api/v1/admin/service-forwards",
        headers=admin_headers,
        json={
            "name": "Embedding API",
            "slug": "model/embedding/v1",
            "source": "tailscale",
            "target_url": "https://lab.tail246500.ts.net/model/v1",
        },
    )

    assert parent_response.status_code == 201
    assert child_response.status_code == 201
    dispatcher = (get_settings().caddy_routes_dir / "active" / "routes.caddy").read_text(encoding="utf-8")
    assert dispatcher.index("# serino-route-path: /model/embedding/v1") < dispatcher.index(
        "# serino-route-path: /model\n"
    )


def test_service_forward_dispatcher_can_be_rebuilt_during_startup(client) -> None:
    from aerisun.domain.service_forwards.service import ensure_route_dispatcher

    settings = get_settings()
    route_path = settings.caddy_routes_dir / "route-existing.caddy"
    route_path.write_text(
        "# serino-route-path: /existing\nhandle @existing {\n    reverse_proxy http://127.0.0.1:9000\n}\n",
        encoding="utf-8",
    )

    ensure_route_dispatcher(settings)

    dispatcher = settings.caddy_routes_dir / "active" / "routes.caddy"
    assert "# serino-route-path: /existing" in dispatcher.read_text(encoding="utf-8")


def test_service_forward_admin_endpoints_require_authentication(client) -> None:
    response = client.get("/api/v1/admin/service-forwards")

    assert response.status_code == 401


def test_admin_list_reuses_existing_sercli_route_files(client, admin_headers) -> None:
    settings = get_settings()
    path = "/files"
    route_id = _route_id("files")
    (settings.caddy_routes_dir / f"route-{route_id}.caddy").write_text(
        "\n".join(
            [
                "# Managed by sercli. This file is local to this server.",
                f"# serino-route-path: {path}",
                "# serino-route-upstream: http://127.0.0.1:9000",
                f"@serino_user_route_{route_id} path {path} {path}/*",
                f"handle @serino_user_route_{route_id} {{",
                "    reverse_proxy http://127.0.0.1:9000",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    response = client.get("/api/v1/admin/service-forwards", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()[0] == {
        "id": route_id,
        "name": "files",
        "slug": "files",
        "path": "/files",
        "source": "custom",
        "target_url": "http://127.0.0.1:9000",
        "public_url": f"{settings.site_url.rstrip('/')}/files",
        "status": "unchecked",
        "checked_at": None,
        "status_message": None,
    }


def test_service_forward_renderer_strips_slug_and_preserves_streams() -> None:
    route_id, upstream, rendered = render_route_file(
        ServiceForwardWrite(
            name="Home Assistant",
            slug="home-assistant",
            source="tailscale",
            target_url="https://lab.tail246500.ts.net/embedding/v1",
        )
    )

    assert route_id == _route_id("home-assistant")
    assert upstream == "https://lab.tail246500.ts.net/embedding/v1"
    assert "path /home-assistant /home-assistant/*" in rendered
    assert "uri replace /home-assistant /embedding/v1 1" in rendered
    assert "reverse_proxy https://lab.tail246500.ts.net" in rendered
    assert "header_up Host {upstream_hostport}" in rendered
    assert "stream_close_delay 5m" in rendered

    _local_id, local_target, local_rendered = render_route_file(
        ServiceForwardWrite(name="Local", slug="local-panel", source="local", port=3000)
    )
    assert local_target == "http://127.0.0.1:3000"
    assert "uri strip_prefix /local-panel" in local_rendered


def test_service_forward_renderer_supports_nested_public_path() -> None:
    route_id, target_url, rendered = render_route_file(
        ServiceForwardWrite(
            name="Embedding API",
            slug="model/embedding/v1",
            source="tailscale",
            target_url="https://lab.tail246500.ts.net/model/v1",
        )
    )

    assert route_id == _route_id("model/embedding/v1")
    assert target_url == "https://lab.tail246500.ts.net/model/v1"
    assert "path /model/embedding/v1 /model/embedding/v1/*" in rendered
    assert "uri replace /model/embedding/v1 /model/v1 1" in rendered


@pytest.mark.parametrize("slug", ("clash.yaml", "proxy/clash.yaml"))
def test_service_forward_renderer_supports_file_like_public_paths(slug: str) -> None:
    route_id, target_url, rendered = render_route_file(
        ServiceForwardWrite(name="Clash config", slug=slug, source="local", port=9090)
    )

    assert route_id == _route_id(slug)
    assert target_url == "http://127.0.0.1:9090"
    assert f"path /{slug} /{slug}/*" in rendered


@pytest.mark.parametrize("slug", (".clash.yaml", "clash.", "clash..yaml", "proxy/.clash.yaml"))
def test_service_forward_rejects_unsafe_file_like_public_paths(slug: str) -> None:
    with pytest.raises(PydanticValidationError):
        ServiceForwardWrite(name="Clash config", slug=slug, source="local", port=9090)


def test_caddy_reload_uses_the_fixed_caddyfile_import(monkeypatch) -> None:
    from aerisun.domain.service_forwards import service

    requests: list[tuple[str, dict]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def post(self, url: str, **kwargs):
            requests.append((url, kwargs))
            return FakeResponse()

    monkeypatch.setattr(service.httpx, "Client", FakeClient)
    settings = get_settings().model_copy(update={"caddy_admin_url": "http://caddy:2019/"})

    service._reload_caddy_config(settings)

    assert requests == [
        (
            "http://caddy:2019/load",
            {
                "content": "import /etc/caddy/Caddyfile\n",
                "headers": {
                    "Content-Type": "text/caddyfile",
                    "Cache-Control": "must-revalidate",
                },
            },
        )
    ]


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        (
            {"name": "API", "slug": "api", "source": "local", "port": 9000},
            "SLUG /api 已由 Serino 使用",
        ),
        (
            {"name": "Private API", "slug": "api/private", "source": "local", "port": 9000},
            "SLUG /api/private 已由 Serino 使用",
        ),
        (
            {
                "name": "Private LAN",
                "slug": "lan",
                "source": "tailscale",
                "target_url": "http://192.168.1.20:8080/private",
            },
            "目标 IP 不属于 Tailscale 地址范围",
        ),
        (
            {
                "name": "Public",
                "slug": "public",
                "source": "tailscale",
                "target_url": "https://example.com/service",
            },
            "请输入 Tailscale IP、MagicDNS 设备名或 .ts.net 地址",
        ),
    ],
)
def test_service_forward_rejects_reserved_or_unsafe_targets(client, admin_headers, payload, detail) -> None:
    response = client.post("/api/v1/admin/service-forwards", headers=admin_headers, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == detail


def test_admin_can_update_probe_and_delete_service_forward(client, admin_headers, monkeypatch) -> None:
    created = client.post(
        "/api/v1/admin/service-forwards",
        headers=admin_headers,
        json={"name": "Panel", "slug": "panel", "source": "local", "port": 8080},
    ).json()

    update_response = client.put(
        f"/api/v1/admin/service-forwards/{created['id']}",
        headers=admin_headers,
        json={
            "name": "NAS Panel",
            "slug": "nas",
            "source": "tailscale",
            "target_url": "https://lab.tail246500.ts.net/embedding/v1",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["id"] == _route_id("nas")
    assert updated["target_url"] == "https://lab.tail246500.ts.net/embedding/v1"
    assert updated["status"] == "unchecked"

    monkeypatch.setattr(
        "aerisun.domain.service_forwards.service._probe_target",
        lambda _target_url: ("reachable", "目标服务返回 HTTP 401"),
    )
    probe_response = client.post(
        f"/api/v1/admin/service-forwards/{updated['id']}/test",
        headers=admin_headers,
    )

    assert probe_response.status_code == 200
    assert probe_response.json()["status"] == "reachable"
    assert probe_response.json()["status_message"] == "目标服务返回 HTTP 401"
    assert probe_response.json()["checked_at"] is not None

    listed = client.get("/api/v1/admin/service-forwards", headers=admin_headers).json()
    assert listed[0]["status"] == "reachable"

    delete_response = client.delete(
        f"/api/v1/admin/service-forwards/{updated['id']}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 204
    assert client.get("/api/v1/admin/service-forwards", headers=admin_headers).json() == []


def test_create_rolls_back_file_when_caddy_reload_fails(client, admin_headers, monkeypatch) -> None:
    from aerisun.domain.service_forwards import service

    def fail_reload(_settings) -> None:
        raise RuntimeError("caddy rejected config")

    monkeypatch.setattr(service, "_reload_caddy_config", fail_reload, raising=False)

    response = client.post(
        "/api/v1/admin/service-forwards",
        headers=admin_headers,
        json={"name": "Broken", "slug": "broken", "source": "local", "port": 9999},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Caddy 未能加载服务转发配置，已恢复原配置"
    assert client.get("/api/v1/admin/service-forwards", headers=admin_headers).json() == []
    assert not (get_settings().caddy_routes_dir / "active" / "routes.caddy").exists()


def test_update_and_delete_restore_the_previous_route_when_reload_fails(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    from aerisun.domain.service_forwards import service

    created = client.post(
        "/api/v1/admin/service-forwards",
        headers=admin_headers,
        json={"name": "Panel", "slug": "panel", "source": "local", "port": 8080},
    ).json()
    dispatcher_path = get_settings().caddy_routes_dir / "active" / "routes.caddy"
    original_dispatcher = dispatcher_path.read_bytes()

    def fail_reload(_settings) -> None:
        raise RuntimeError("caddy rejected config")

    monkeypatch.setattr(service, "_reload_caddy_config", fail_reload)

    update_response = client.put(
        f"/api/v1/admin/service-forwards/{created['id']}",
        headers=admin_headers,
        json={"name": "New Panel", "slug": "new-panel", "source": "local", "port": 9090},
    )

    assert update_response.status_code == 503
    assert client.get("/api/v1/admin/service-forwards", headers=admin_headers).json() == [created]
    assert dispatcher_path.read_bytes() == original_dispatcher

    delete_response = client.delete(
        f"/api/v1/admin/service-forwards/{created['id']}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 503
    assert client.get("/api/v1/admin/service-forwards", headers=admin_headers).json() == [created]
    assert dispatcher_path.read_bytes() == original_dispatcher
