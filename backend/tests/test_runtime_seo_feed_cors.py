from __future__ import annotations

import xml.etree.ElementTree as ET

from sqlalchemy import text

from aerisun.core.middleware import _resolve_allowed_origins


def test_sitemap_xml_uses_runtime_public_site_url_and_static_pages(client, admin_headers):
    client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "public_site_url": "https://aerisun.example.com/",
            "production_cors_origins": ["https://aerisun.example.com"],
            "seo_default_title": "Aerisun",
            "seo_default_description": "Aerisun desc",
            "rss_title": "Aerisun Feed",
            "rss_description": "Feed desc",
            "robots_indexing_enabled": True,
            "sitemap_static_pages": [
                {"path": "/", "changefreq": "daily", "priority": "1.0"},
                {"path": "/about", "changefreq": "weekly", "priority": "0.6"},
            ],
        },
    )

    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]

    root = ET.fromstring(r.text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [url.find("sm:loc", ns).text for url in root.findall("sm:url", ns)]

    assert "https://aerisun.example.com/" in urls
    assert "https://aerisun.example.com/about" in urls
    assert all(url.startswith("https://aerisun.example.com") for url in urls)


def test_robots_txt_uses_runtime_public_site_url_and_indexing_toggle(client, admin_headers):
    client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "public_site_url": "https://aerisun.example.com",
            "production_cors_origins": ["https://aerisun.example.com"],
            "seo_default_title": "Aerisun",
            "seo_default_description": "Aerisun desc",
            "rss_title": "Aerisun Feed",
            "rss_description": "Feed desc",
            "robots_indexing_enabled": False,
            "sitemap_static_pages": [{"path": "/", "changefreq": "daily", "priority": "1.0"}],
        },
    )

    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /" in r.text
    assert "Sitemap: https://aerisun.example.com/sitemap.xml" in r.text


def test_posts_feed_uses_runtime_public_site_url_and_rss_copy(client, admin_headers):
    client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "public_site_url": "https://aerisun.example.com/",
            "production_cors_origins": ["https://aerisun.example.com"],
            "seo_default_title": "Aerisun",
            "seo_default_description": "Aerisun desc",
            "rss_title": "Aerisun Feed",
            "rss_description": "Latest updates from Aerisun",
            "robots_indexing_enabled": True,
            "sitemap_static_pages": [{"path": "/", "changefreq": "daily", "priority": "1.0"}],
        },
    )

    response = client.get("/feeds/posts.xml")
    assert response.status_code == 200
    assert "application/rss+xml" in response.headers["content-type"]
    assert "<title>Aerisun Feed</title>" in response.text
    assert "<description>Latest updates from Aerisun</description>" in response.text
    assert 'href="https://aerisun.example.com/feeds/posts.xml"' in response.text
    assert "<link>https://aerisun.example.com/posts</link>" in response.text


def test_admin_feed_links_use_runtime_public_site_url(client, admin_headers):
    client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "public_site_url": "https://aerisun.example.com",
            "production_cors_origins": ["https://aerisun.example.com"],
            "seo_default_title": "Aerisun",
            "seo_default_description": "Aerisun desc",
            "rss_title": "Aerisun Feed",
            "rss_description": "Feed desc",
            "robots_indexing_enabled": True,
            "sitemap_static_pages": [{"path": "/", "changefreq": "daily", "priority": "1.0"}],
        },
    )

    response = client.get("/api/v1/admin/integrations/feeds", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == [
        {
            "key": "posts",
            "title": "Posts RSS",
            "url": "https://aerisun.example.com/feeds/posts.xml",
            "enabled": True,
            "format": "rss",
        },
        {
            "key": "rss",
            "title": "RSS Alias",
            "url": "https://aerisun.example.com/rss.xml",
            "enabled": True,
            "format": "rss",
        },
    ]


def test_production_runtime_cors_allowlist_is_used_for_preflight(client, admin_headers, monkeypatch):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://fallback.example.com"]')

    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        session.execute(
            text("UPDATE runtime_site_settings SET production_cors_origins = :origins"),
            {"origins": '["https://app.example.com", "https://admin.example.com"]'},
        )
        session.commit()

        assert _resolve_allowed_origins(settings, session) == [
            "https://app.example.com",
            "https://admin.example.com",
        ]


def test_runtime_settings_update_invalidates_sitemap_cache(client, admin_headers):
    first = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "public_site_url": "https://aerisun.example.com",
            "production_cors_origins": ["https://aerisun.example.com"],
            "seo_default_title": "Aerisun",
            "seo_default_description": "Aerisun desc",
            "rss_title": "Aerisun Feed",
            "rss_description": "Feed desc",
            "robots_indexing_enabled": True,
            "sitemap_static_pages": [{"path": "/before", "changefreq": "daily", "priority": "1.0"}],
        },
    )
    assert first.status_code == 200

    sitemap_before = client.get("/sitemap.xml")
    assert sitemap_before.status_code == 200
    assert "https://aerisun.example.com/before" in sitemap_before.text

    second = client.put(
        "/api/v1/admin/site-config/runtime",
        headers=admin_headers,
        json={
            "sitemap_static_pages": [{"path": "/after", "changefreq": "daily", "priority": "1.0"}],
        },
    )
    assert second.status_code == 200

    sitemap_after = client.get("/sitemap.xml")
    assert sitemap_after.status_code == 200
    assert "https://aerisun.example.com/after" in sitemap_after.text
    assert "https://aerisun.example.com/before" not in sitemap_after.text


def test_resolve_allowed_origins_prefers_runtime_list_in_production(seeded_session, monkeypatch):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://fallback.example.com"]')

    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        session.execute(
            text("UPDATE runtime_site_settings SET production_cors_origins = :origins"),
            {"origins": '["https://app.example.com"]'},
        )
        session.commit()

    with factory() as session:
        assert _resolve_allowed_origins(settings, session) == ["https://app.example.com"]
