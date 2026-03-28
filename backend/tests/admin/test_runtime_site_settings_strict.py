from __future__ import annotations


def test_runtime_site_settings_partial_update_and_trim(client, admin_headers) -> None:
    # Establish baseline
    baseline = client.get("/api/v1/admin/site-config/runtime", headers=admin_headers)
    assert baseline.status_code == 200
    baseline_payload = baseline.json()

    # Seed a full payload
    full_payload = {
        "public_site_url": "https://aerisun.example.com/",
        "production_cors_origins": ["https://aerisun.example.com", "https://admin.aerisun.example.com"],
        "seo_default_title": "Aerisun Runtime Title",
        "seo_default_description": "Runtime SEO description",
        "rss_title": "Aerisun Feed",
        "rss_description": "Latest updates from Aerisun",
        "robots_indexing_enabled": True,
        "sitemap_static_pages": [
            {"path": "/", "changefreq": "daily", "priority": "1.0"},
            {"path": "/about", "changefreq": "weekly", "priority": "0.6"},
        ],
    }

    seeded = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json=full_payload,
    )
    assert seeded.status_code == 200

    # Trim rule on public_site_url
    url_update = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={"public_site_url": "  https://trimmed.example.com/  "},
    )
    assert url_update.status_code == 200
    url_payload = url_update.json()
    assert url_payload["public_site_url"] == "https://trimmed.example.com/"

    # Partial update: update only rss_title with whitespace
    partial_update = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={"rss_title": "  New RSS Title  "},
    )
    assert partial_update.status_code == 200
    partial_payload = partial_update.json()

    # Trim rule
    assert partial_payload["rss_title"] == "New RSS Title"

    # Unspecified fields should remain unchanged
    assert partial_payload["public_site_url"] == "https://trimmed.example.com/"
    assert partial_payload["production_cors_origins"] == [
        "https://aerisun.example.com",
        "https://admin.aerisun.example.com",
    ]
    assert partial_payload["seo_default_title"] == "Aerisun Runtime Title"
    assert partial_payload["seo_default_description"] == "Runtime SEO description"
    assert partial_payload["rss_description"] == "Latest updates from Aerisun"
    assert partial_payload["robots_indexing_enabled"] is True
    assert partial_payload["sitemap_static_pages"] == full_payload["sitemap_static_pages"]

    # Trim + filter rule on origins
    origins_update = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "production_cors_origins": [
                "  https://aerisun.example.com  ",
                "https://admin.aerisun.example.com/",
                "",
                "   ",
            ]
        },
    )
    assert origins_update.status_code == 200
    origins_payload = origins_update.json()

    assert origins_payload["production_cors_origins"] == [
        "https://aerisun.example.com",
        "https://admin.aerisun.example.com/",
    ]

    # Schema-level validation should reject malformed sitemap items before service normalization
    sitemap_update = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "sitemap_static_pages": [
                {"path": "/", "changefreq": "daily", "priority": "1.0"},
                {},
                {"path": "", "changefreq": "weekly", "priority": "0.5"},
                {"path": "no-slash", "changefreq": "weekly", "priority": "0.5"},
                {"path": "/x", "changefreq": "never", "priority": "0.1"},
                {"path": "/x", "changefreq": "daily", "priority": "0.9"},
                {"path": "/bad-priority", "changefreq": "weekly", "priority": "2.5"},
            ]
        },
    )
    assert sitemap_update.status_code == 200
    sitemap_payload = sitemap_update.json()
    assert sitemap_payload["sitemap_static_pages"] == [
        {"path": "/", "changefreq": "daily", "priority": "1.0"},
        {"path": "/x", "changefreq": "never", "priority": "0.1"},
        {"path": "/bad-priority", "changefreq": "weekly", "priority": "1.0"},
    ]

    # Restore baseline (best effort so this test doesn't pollute subsequent ones)
    client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "public_site_url": baseline_payload.get("public_site_url", ""),
            "production_cors_origins": baseline_payload.get("production_cors_origins", []),
            "seo_default_title": baseline_payload.get("seo_default_title", ""),
            "seo_default_description": baseline_payload.get("seo_default_description", ""),
            "rss_title": baseline_payload.get("rss_title", ""),
            "rss_description": baseline_payload.get("rss_description", ""),
            "robots_indexing_enabled": baseline_payload.get("robots_indexing_enabled", True),
            "sitemap_static_pages": baseline_payload.get("sitemap_static_pages", []),
        },
    )
