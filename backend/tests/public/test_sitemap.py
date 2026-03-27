from __future__ import annotations

import xml.etree.ElementTree as ET


def test_sitemap_returns_xml(client):
    resp = client.get("/api/v1/site/sitemap.xml")
    assert resp.status_code == 200
    assert "xml" in resp.headers.get("content-type", "")
    # 验证 XML 有效
    root = ET.fromstring(resp.text)
    assert root.tag.endswith("urlset")


def test_sitemap_contains_static_pages(client):
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
