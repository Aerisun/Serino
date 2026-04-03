from __future__ import annotations

import httpx
import pytest
import respx


@pytest.fixture(autouse=True)
def reset_hitokoto_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from aerisun.domain.site_config import service as site_service

    with site_service._HITOKOTO_CACHE_LOCK:
        site_service._HITOKOTO_CACHE.clear()
        site_service._HITOKOTO_CACHE_REFRESHING.clear()
    with site_service._LINK_PREVIEW_CACHE_LOCK:
        site_service._LINK_PREVIEW_CACHE.clear()
    with site_service._HITOKOTO_REQUEST_LOCK:
        site_service._HITOKOTO_NEXT_REQUEST_AT = 0.0

    monkeypatch.setattr(site_service, "HITOKOTO_REQUEST_INTERVAL_SECONDS", 0.0)


def test_read_site_returns_seeded_payload(client) -> None:
    response = client.get("/api/v1/site/site")

    assert response.status_code == 200

    payload = response.json()
    assert payload["site"]["name"] == "Felix"
    assert payload["site"]["title"] == "Aerisun"
    assert {"footer_text", "author", "meta_description", "copyright"} & payload["site"].keys() == set()
    assert "site_icon_url" in payload["site"]
    assert payload["site"]["hero_video_url"] == (
        "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
        "hf_20260306_115329_5e00c9c5-4d69-49b7-94c3-9c31c60bb644.mp4"
    )
    assert len(payload["social_links"]) >= 1
    assert len(payload["poems"]) == 12


def test_read_site_hides_internal_automation_feature_flags(client) -> None:
    response = client.get("/api/v1/site/site")

    assert response.status_code == 200

    feature_flags = dict(response.json()["site"]["feature_flags"] or {})
    assert "agent_model_config" not in feature_flags
    assert "agent_workflows" not in feature_flags
    assert "agent_workflow_draft" not in feature_flags
    assert "agent_surface_drafts" not in feature_flags
    assert "mcp_public_access" not in feature_flags


def test_read_site_manifest_uses_configured_site_icon(client) -> None:
    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")

    payload = response.json()
    assert payload["name"] == "Aerisun"
    assert payload["short_name"] == "Felix"
    assert payload["description"] == "我做网页设计，也写前端，把视觉、节奏、内容和交互整理成一个自然流动的个人空间。"
    assert payload["icons"][0]["src"] == "/media/internal/assets/site-icon/90db1b781930.svg"


@respx.mock
def test_read_poem_preview_defaults_to_hitokoto(client) -> None:
    respx.get("https://v1.hitokoto.cn/").mock(
        return_value=httpx.Response(
            200,
            json={
                "hitokoto": "我见青山多妩媚",
                "from": "贺新郎",
                "from_who": "辛弃疾",
            },
        )
    )

    response = client.get("/api/v1/site/poem-preview")

    assert response.status_code == 200

    payload = response.json()
    assert payload["mode"] == "hitokoto"
    assert payload["content"] == "我见青山多妩媚"
    assert payload["attribution"] == "辛弃疾 · 贺新郎"


@respx.mock
def test_read_poem_preview_fetches_hitokoto_server_side(client) -> None:
    respx.get("https://v1.hitokoto.cn/").mock(
        return_value=httpx.Response(
            200,
            json={
                "hitokoto": "纸上得来终觉浅",
                "from": "冬夜读书示子聿",
                "from_who": "陆游",
            },
        )
    )

    response = client.get(
        "/api/v1/site/poem-preview",
        params=[
            ("mode", "hitokoto"),
            ("strict", "true"),
            ("types", "i"),
        ],
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["mode"] == "hitokoto"
    assert payload["content"] == "纸上得来终觉浅"
    assert payload["attribution"] == "陆游 · 冬夜读书示子聿"


@respx.mock
def test_read_poem_preview_refills_cache_when_buffer_drops_to_threshold(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aerisun.domain.site_config import service as site_service

    class ImmediateThread:
        def __init__(self, *, target, daemon: bool) -> None:
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(site_service, "Thread", ImmediateThread)

    route = respx.get("https://v1.hitokoto.cn/").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "hitokoto": f"缓存诗句 {index}",
                    "from": "cache-buffer 来源",
                    "from_who": "缓存作者",
                },
            )
            for index in range(25)
        ]
    )

    params = {"mode": "hitokoto", "strict": "true"}
    responses = [client.get("/api/v1/site/poem-preview", params=params) for _ in range(5)]

    assert all(response.status_code == 200 for response in responses)
    assert [response.json()["content"] for response in responses] == [
        "缓存诗句 0",
        "缓存诗句 1",
        "缓存诗句 2",
        "缓存诗句 3",
        "缓存诗句 4",
    ]
    assert route.call_count == 25

    cache_key = site_service._build_hitokoto_cache_key(list(site_service.DEFAULT_HITOKOTO_TYPES))
    with site_service._HITOKOTO_CACHE_LOCK:
        queue = site_service._HITOKOTO_CACHE.get(cache_key)
        assert queue is not None
        assert len(queue) == 20
        assert str(queue[0].content) == "缓存诗句 5"


@respx.mock
def test_read_poem_preview_does_not_retry_for_keywords_anymore(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aerisun.domain.site_config import service as site_service

    monkeypatch.setattr(site_service, "HITOKOTO_CACHE_SIZE", 1)
    monkeypatch.setattr(site_service, "HITOKOTO_CACHE_REFILL_THRESHOLD", -1)

    route = respx.get("https://v1.hitokoto.cn/").mock(
        return_value=httpx.Response(
            200,
            json={
                "hitokoto": "春风不度玉门关",
                "from": "凉州词",
                "from_who": "王之涣",
            },
        )
    )

    response = client.get(
        "/api/v1/site/poem-preview",
        params=[
            ("mode", "hitokoto"),
            ("strict", "true"),
            ("types", "i"),
            ("keywords", "婉约"),
        ],
    )

    assert response.status_code == 200
    assert response.json()["content"] == "春风不度玉门关"
    assert route.call_count == 1


def test_hitokoto_rate_limit_spaces_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    from aerisun.domain.site_config import service as site_service

    with site_service._HITOKOTO_REQUEST_LOCK:
        site_service._HITOKOTO_NEXT_REQUEST_AT = 0.0

    sleep_calls: list[float] = []
    clock_values = iter([10.0, 10.1, 10.5])

    monkeypatch.setattr(site_service, "HITOKOTO_REQUEST_INTERVAL_SECONDS", 0.5)
    monkeypatch.setattr(site_service, "monotonic", lambda: next(clock_values))
    monkeypatch.setattr(site_service, "sleep", lambda seconds: sleep_calls.append(seconds))

    site_service._wait_for_hitokoto_request_slot()
    site_service._wait_for_hitokoto_request_slot()

    assert sleep_calls == [pytest.approx(0.4)]
    assert pytest.approx(11.0) == site_service._HITOKOTO_NEXT_REQUEST_AT


@respx.mock
def test_read_poem_preview_falls_back_to_custom_when_hitokoto_fails(client) -> None:
    respx.get("https://v1.hitokoto.cn/").mock(return_value=httpx.Response(503))

    response = client.get(
        "/api/v1/site/poem-preview",
        params={"mode": "hitokoto"},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["mode"] == "custom"
    assert isinstance(payload["content"], str)
    assert payload["content"]


@respx.mock
def test_read_poem_preview_strict_mode_returns_error_when_hitokoto_fails(client) -> None:
    respx.get("https://v1.hitokoto.cn/").mock(return_value=httpx.Response(503))

    response = client.get(
        "/api/v1/site/poem-preview",
        params={"mode": "hitokoto", "strict": "true"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "在线诗句获取失败，请稍后重试。"


@respx.mock
def test_read_link_preview_returns_open_graph_metadata(client, monkeypatch: pytest.MonkeyPatch) -> None:
    from aerisun.domain.site_config import service as site_service

    preview_url = "https://example.com/post"
    monkeypatch.setattr(site_service, "_ensure_public_link_preview_url", lambda value: value)

    html = """
    <html>
      <head>
        <title>Fallback Title</title>
        <meta property="og:title" content="Open Graph Title" />
        <meta property="og:description" content="A rich preview description." />
        <meta property="og:site_name" content="Example Site" />
        <meta property="og:image" content="/images/social-card.png" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>Hello</body>
    </html>
    """

    respx.get(preview_url).mock(
        return_value=httpx.Response(
            200,
            text=html,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", preview_url),
        )
    )

    response = client.get("/api/v1/site/link-preview", params={"url": preview_url})

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["title"] == "Open Graph Title"
    assert payload["description"] == "A rich preview description."
    assert payload["site_name"] == "Example Site"
    assert payload["image_url"] == "https://example.com/images/social-card.png"
    assert payload["image_width"] is None
    assert payload["image_height"] is None
    assert payload["icon_url"] == "https://example.com/favicon.ico"


def test_read_link_preview_rejects_private_hosts(client) -> None:
    response = client.get("/api/v1/site/link-preview", params={"url": "http://127.0.0.1/internal"})

    assert response.status_code == 422
    assert response.json()["detail"] == "不支持本地或内网地址的链接预览。"
