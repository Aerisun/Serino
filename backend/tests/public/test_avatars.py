def test_read_notionists_avatar_returns_generated_svg(client) -> None:
    response = client.get("/api/v1/avatars/10.x/notionists/svg", params={"seed": "55fc3d39"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.text.startswith("<svg")
    assert "<svg" in response.text


def test_read_notionists_avatar_is_deterministic_by_seed(client) -> None:
    first = client.get("/api/v1/avatars/10.x/notionists/svg", params={"seed": "same-seed"})
    second = client.get("/api/v1/avatars/10.x/notionists/svg", params={"seed": "same-seed"})
    different = client.get("/api/v1/avatars/10.x/notionists/svg", params={"seed": "different-seed"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert different.status_code == 200
    assert first.text == second.text
    assert first.text != different.text


def test_render_notionists_avatar_uses_small_lru_cache(monkeypatch) -> None:
    from aerisun.domain.avatars import service

    service._cached_render_notionists_svg.cache_clear()

    calls: list[str] = []

    def fake_render(seed: str) -> str:
        calls.append(seed)
        return f"<svg>{seed}</svg>"

    monkeypatch.setattr(service, "_render_notionists_svg_uncached", fake_render)

    assert service.render_notionists_svg("same-seed") == "<svg>same-seed</svg>"
    assert service.render_notionists_svg("same-seed") == "<svg>same-seed</svg>"
    assert service.render_notionists_svg("different-seed") == "<svg>different-seed</svg>"
    assert service._cached_render_notionists_svg.cache_info().maxsize == 256
    assert calls == ["same-seed", "different-seed"]

    service._cached_render_notionists_svg.cache_clear()
