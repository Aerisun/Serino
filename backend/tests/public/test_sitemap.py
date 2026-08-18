from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import timedelta

from aerisun.core.db import get_session_factory
from aerisun.domain.content.seo_service import _CACHE_TTL, _sitemap_cache
from aerisun.domain.diary_access.service import DIARY_PRIVATE_FEATURE_FLAG
from aerisun.domain.site_config.models import ResumeBasics, SiteProfile


def _set_diary_private_enabled(enabled: bool) -> None:
    with get_session_factory()() as session:
        profile = session.query(SiteProfile).one()
        flags = dict(profile.feature_flags or {})
        flags[DIARY_PRIVATE_FEATURE_FLAG] = enabled
        profile.feature_flags = flags
        session.commit()


def test_sitemap_returns_xml(client):
    resp = client.get("/api/v1/site/sitemap.xml")
    assert resp.status_code == 200
    assert "xml" in resp.headers.get("content-type", "")
    # 验证 XML 有效
    root = ET.fromstring(resp.text)
    assert root.tag.endswith("urlset")


def test_sitemap_contains_static_pages(client):
    _set_diary_private_enabled(False)
    resp = client.get("/api/v1/site/sitemap.xml")
    root = ET.fromstring(resp.text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [url.find("sm:loc", ns).text for url in root.findall("sm:url", ns)]
    # 种子数据中 site_url 默认是 http://localhost:5173
    # 检查至少包含一些静态页面路径
    paths = [u.split("/", 3)[-1] if "/" in u[8:] else "" for u in urls]
    assert any("posts" in p for p in paths)
    assert any("diary" in p for p in paths)


def test_sitemap_contains_published_posts(client):
    resp = client.get("/api/v1/site/sitemap.xml")
    root = ET.fromstring(resp.text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [url.find("sm:loc", ns).text for url in root.findall("sm:url", ns)]
    # 种子数据有 8 篇已发布的 post，应该在 sitemap 中有对应的详情 URL
    # 详情 URL 格式: http://localhost:5173/posts/<slug>
    # 列表 URL 格式: http://localhost:5173/posts (无尾部斜杠和 slug)
    post_detail_urls = [u for u in urls if "/posts/" in u and not u.endswith("/posts/")]
    assert len(post_detail_urls) >= 1  # 至少有种子数据的文章


def test_sitemap_includes_public_non_rss_notes_under_their_own_path(client, admin_headers):
    _sitemap_cache.clear()
    created = client.post(
        "/api/v1/admin/posts/",
        json={
            "slug": "sitemap-note-not-in-rss",
            "title": "站点地图中的手记",
            "body": "这篇手记不进入 RSS，但仍应公开可发现。",
            "visibility": "public",
            "kind": "note",
            "exclude_from_rss": True,
        },
        headers=admin_headers,
    )
    assert created.status_code == 201

    response = client.get("/api/v1/site/sitemap.xml")

    assert response.status_code == 200
    assert "/notes" in response.text
    assert "/notes/sitemap-note-not-in-rss" in response.text


def test_sitemap_identity_pages_use_real_lastmod_and_bypass_stale_cache(client):
    _sitemap_cache.clear()
    with get_session_factory()() as session:
        profile = session.query(SiteProfile).one()
        resume = session.query(ResumeBasics).one()
        expected_home_lastmod = profile.updated_at.strftime("%Y-%m-%d")
        expected_resume_lastmod = resume.updated_at.strftime("%Y-%m-%d")

    first = client.get("/api/v1/site/sitemap.xml")
    assert first.status_code == 200
    root = ET.fromstring(first.text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    entries = {
        url.find("sm:loc", ns).text: url.find("sm:lastmod", ns).text if url.find("sm:lastmod", ns) is not None else None
        for url in root.findall("sm:url", ns)
    }
    assert entries["http://localhost:8080/"] == expected_home_lastmod
    assert entries["http://localhost:8080/resume"] == expected_resume_lastmod

    with get_session_factory()() as session:
        profile = session.query(SiteProfile).one()
        profile.updated_at = profile.updated_at + timedelta(days=1)
        expected_updated_lastmod = profile.updated_at.strftime("%Y-%m-%d")
        session.commit()

    second = client.get("/api/v1/site/sitemap.xml")
    second_root = ET.fromstring(second.text)
    second_entries = {
        url.find("sm:loc", ns).text: url.find("sm:lastmod", ns).text if url.find("sm:lastmod", ns) is not None else None
        for url in second_root.findall("sm:url", ns)
    }
    assert second_entries["http://localhost:8080/"] == expected_updated_lastmod


def test_sitemap_prunes_expired_revision_cache_entries(client):
    now = time.monotonic()
    _sitemap_cache.clear()
    _sitemap_cache["expired-revision"] = (now - _CACHE_TTL - 1, "expired")
    _sitemap_cache["fresh-revision"] = (now, "fresh")

    response = client.get("/api/v1/site/sitemap.xml")

    assert response.status_code == 200
    assert "expired-revision" not in _sitemap_cache
    assert "fresh-revision" in _sitemap_cache
