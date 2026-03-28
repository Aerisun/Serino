from __future__ import annotations


def test_admin_runtime_site_settings_round_trip(client, admin_headers) -> None:
    response = client.get("/api/v1/admin/site-config/runtime", headers=admin_headers)
    assert response.status_code == 200
    current = response.json()

    assert current["public_site_url"] in {"", "http://localhost:5173"}
    assert current["production_cors_origins"] == []
    assert current["seo_default_title"] == "Aerisun"
    assert current["rss_title"] == "Aerisun"
    assert current["robots_indexing_enabled"] is True
    assert any(item["path"] == "/posts" for item in current["sitemap_static_pages"])

    payload = {
        "public_site_url": "https://aerisun.example.com/",
        "production_cors_origins": [
            "https://aerisun.example.com ",
            " https://admin.aerisun.example.com",
            "",
        ],
        "seo_default_title": "Aerisun Runtime Title",
        "seo_default_description": "Runtime SEO description",
        "rss_title": "Aerisun Feed",
        "rss_description": "Latest updates from Aerisun",
        "robots_indexing_enabled": False,
        "sitemap_static_pages": [
            {"path": "/", "changefreq": "daily", "priority": "1.0"},
            {"path": "/about", "changefreq": "weekly", "priority": "0.6"},
        ],
    }

    update_response = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json=payload,
    )
    assert update_response.status_code == 200
    updated = update_response.json()

    assert updated["public_site_url"] == "https://aerisun.example.com/"
    assert updated["production_cors_origins"] == [
        "https://aerisun.example.com",
        "https://admin.aerisun.example.com",
    ]
    assert updated["seo_default_title"] == payload["seo_default_title"]
    assert updated["seo_default_description"] == payload["seo_default_description"]
    assert updated["rss_title"] == payload["rss_title"]
    assert updated["rss_description"] == payload["rss_description"]
    assert updated["robots_indexing_enabled"] is False
    assert updated["sitemap_static_pages"] == payload["sitemap_static_pages"]

    refreshed = client.get("/api/v1/admin/site-config/runtime", headers=admin_headers)
    assert refreshed.status_code == 200
    persisted = refreshed.json()
    assert persisted["production_cors_origins"] == [
        "https://aerisun.example.com",
        "https://admin.aerisun.example.com",
    ]
    assert persisted["robots_indexing_enabled"] is False


def test_public_site_config_includes_runtime_settings(client, admin_headers) -> None:
    client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "public_site_url": "https://aerisun.example.com",
            "production_cors_origins": ["https://aerisun.example.com"],
            "seo_default_title": "Aerisun Runtime Title",
            "seo_default_description": "Runtime SEO description",
            "rss_title": "Aerisun Feed",
            "rss_description": "Latest updates from Aerisun",
            "robots_indexing_enabled": True,
            "sitemap_static_pages": [
                {"path": "/", "changefreq": "daily", "priority": "1.0"},
                {"path": "/archive", "changefreq": "weekly", "priority": "0.4"},
            ],
        },
    )

    response = client.get("/api/v1/site/site")
    assert response.status_code == 200
    payload = response.json()

    assert payload["runtime"]["public_site_url"] == "https://aerisun.example.com"
    assert payload["runtime"]["production_cors_origins"] == ["https://aerisun.example.com"]
    assert payload["runtime"]["seo_default_title"] == "Aerisun Runtime Title"
    assert payload["runtime"]["seo_default_description"] == "Runtime SEO description"
    assert payload["runtime"]["rss_title"] == "Aerisun Feed"
    assert payload["runtime"]["rss_description"] == "Latest updates from Aerisun"
    assert payload["runtime"]["robots_indexing_enabled"] is True
    assert payload["runtime"]["sitemap_static_pages"][1]["path"] == "/archive"
