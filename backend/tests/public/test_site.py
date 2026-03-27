from __future__ import annotations

import httpx
import respx


def test_read_site_returns_seeded_payload(client) -> None:
    response = client.get("/api/v1/site/site")

    assert response.status_code == 200

    payload = response.json()
    assert payload["site"]["name"] == "Felix"
    assert payload["site"]["title"] == "Aerisun"
    assert "site_icon_url" in payload["site"]
    assert len(payload["social_links"]) >= 1
    assert len(payload["poems"]) == 12


def test_read_poem_preview_returns_seeded_custom_poem(client) -> None:
    response = client.get("/api/v1/site/poem-preview")

    assert response.status_code == 200

    payload = response.json()
    assert payload["mode"] == "custom"
    assert isinstance(payload["content"], str)
    assert payload["content"]


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
            ("keywords", "陆游"),
        ],
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["mode"] == "hitokoto"
    assert payload["content"] == "纸上得来终觉浅"
    assert payload["attribution"] == "陆游 · 冬夜读书示子聿"


@respx.mock
def test_read_poem_preview_uses_prefetched_cache_buffer(client) -> None:
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
            for index in range(20)
        ]
    )

    first = client.get(
        "/api/v1/site/poem-preview",
        params={"mode": "hitokoto", "strict": "true", "keywords": "cache-buffer"},
    )
    second = client.get(
        "/api/v1/site/poem-preview",
        params={"mode": "hitokoto", "strict": "true", "keywords": "cache-buffer"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["mode"] == "hitokoto"
    assert second.json()["mode"] == "hitokoto"
    assert route.call_count == 20


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
