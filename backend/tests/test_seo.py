from __future__ import annotations

import json
import re

from aerisun.core.db import get_session_factory
from aerisun.domain.content.seo_service import build_robots_txt
from aerisun.domain.site_config.models import SiteProfile


def configure_search_identity(**search_optimization: str) -> None:
    factory = get_session_factory()
    with factory() as session:
        profile = session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
        assert profile is not None
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            "search_optimization": search_optimization,
        }
        session.commit()


def read_json_ld_graph(html: str) -> list[dict[str, object]]:
    match = re.search(r'<script type="application/ld\+json">(.+?)</script>', html)
    assert match is not None
    payload = json.loads(match.group(1))
    graph = payload["@graph"]
    assert isinstance(graph, list)
    return graph


def test_sitemap_xml(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    assert '<?xml version="1.0"' in r.text
    assert "<urlset" in r.text
    assert "<loc>" in r.text
    assert "/calendar" not in r.text


def test_robots_txt(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "User-agent: *" in r.text
    assert "Disallow: /admin/" in r.text
    assert "Disallow: /api/v1/admin/" in r.text
    assert "Disallow: /api/mcp" in r.text
    assert "Sitemap:" in r.text


def test_robots_txt_balances_ai_discovery_and_training_opt_out(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200

    for user_agent in (
        "Googlebot",
        "bingbot",
        "Baiduspider",
        "Bytespider",
        "DoubaoBot",
        "OAI-SearchBot",
        "ChatGPT-User",
        "PerplexityBot",
        "Claude-SearchBot",
        "Claude-User",
        "GoogleOther",
        "Google-InspectionTool",
        "Google-Agent",
        "Google-NotebookLM",
        "Google-Read-Aloud",
    ):
        assert f"User-agent: {user_agent}\nAllow: /" in r.text

    for user_agent in ("GPTBot", "Google-Extended", "ClaudeBot", "CCBot"):
        assert f"User-agent: {user_agent}\nDisallow: /" in r.text


def test_robots_txt_uses_configured_admin_base_path():
    content = build_robots_txt(
        "https://example.com",
        admin_base_path="/control-room/",
        api_base_path="/api",
    )

    assert "Disallow: /control-room/" in content
    assert "Disallow: /admin/" not in content


def test_llms_txt_guides_ai_agents_to_person_and_public_content(client):
    r = client.get("/llms.txt")
    assert r.status_code == 200
    assert "markdown" in r.headers["content-type"] or "text/plain" in r.headers["content-type"]
    assert r.text.startswith("# ")
    assert "## Start here" in r.text
    assert "[Resume Markdown](" in r.text
    assert "/resume.md" in r.text
    assert "/resume" in r.text
    assert "/api/v1/site/bootstrap" in r.text
    assert "/api/v1/site/resume" in r.text
    assert "/api/v1/site/posts" in r.text
    start_here = r.text.split("## Start here", 1)[1].split("## Machine-readable public data", 1)[0]
    assert "[Diary](" in start_here
    assert "/diary" in start_here
    assert "For public writing, read the crawler-readable HTML pages first." in r.text
    assert "Open /posts/{slug} and /diary/{slug} only when you need a full single-entry page." in r.text
    assert "Use RSS feeds as update signals, not as the primary source of full content." in r.text
    assert "/feeds/posts.xml" in r.text
    assert "/feeds/thoughts.xml" in r.text
    assert "/feeds/diary.xml" in r.text
    assert "/feeds/excerpts.xml" in r.text
    assert "/sitemap.xml" in r.text
    assert "/robots.txt" in r.text
    assert "/admin" not in r.text


def test_resume_markdown_exposes_resume_without_spa(client):
    r = client.get("/resume.md")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert r.text.startswith("# Felix")
    assert "## Summary" in r.text
    assert "上海 / Remote" in r.text
    assert "felix@example.com" in r.text


def test_resume_markdown_head_supports_resource_probes(client):
    r = client.head("/resume.md")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert r.text == ""


def test_llms_txt_head_supports_resource_probes(client):
    r = client.head("/llms.txt")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert r.text == ""


def test_llms_txt_is_available_under_site_api_prefix(client):
    r = client.get("/api/v1/site/llms.txt")
    assert r.status_code == 200
    assert "# " in r.text
    assert "/resume.md" in r.text


def test_resume_markdown_is_available_under_site_api_prefix(client):
    r = client.get("/api/v1/site/resume.md")
    assert r.status_code == 200
    assert "# Felix" in r.text


def test_home_seo_html_exposes_public_profile_in_app_shell(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert r.text.lower().startswith("<!doctype html>")
    assert '<div id="root">' in r.text
    assert 'data-seo-shell="home"' in r.text
    assert 'type="module"' in r.text
    assert "站点加载中" not in r.text
    assert "Felix" in r.text
    assert "/resume" in r.text
    assert "/resume.md" in r.text
    assert "/llms.txt" in r.text
    assert "/feeds/posts.xml" in r.text
    assert "/feeds/diary.xml" in r.text
    assert "/posts" in r.text
    assert '<a href="http://localhost:8080/diary">Diary</a>' in r.text
    assert 'href="http://localhost:8080/feeds/diary.xml" title="Latest public diary entries"' in r.text
    assert "application/ld+json" in r.text
    assert "WebSite" in r.text
    assert "Person" in r.text
    assert "This is the personal website, blog, and public work archive for Felix (Aerisun)." in r.text
    assert "Aerisun is the personal website, blog, and public work archive for Felix." not in r.text


def test_home_seo_html_promotes_configured_real_name_without_changing_browser_title(client):
    configure_search_identity(real_name="测试姓名", meta_title="测试搜索标题")

    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Aerisun</title>" in r.text
    assert '<meta property="og:title" content="测试搜索标题">' in r.text
    assert '<meta name="author" content="测试姓名">' in r.text
    assert 'content="测试姓名（Aerisun）' in r.text
    assert "测试姓名（Aerisun）。" in r.text

    graph = read_json_ld_graph(r.text)
    person = next(item for item in graph if item.get("@type") == "Person")
    website = next(item for item in graph if item.get("@type") == "WebSite")
    assert person["name"] == "测试姓名"
    assert "Aerisun" in person["alternateName"]
    assert website["about"] == {"@id": "http://localhost:8080/#person"}
    assert website["mainEntity"] == {"@id": "http://localhost:8080/#person"}


def test_home_seo_shell_keeps_react_mount_before_crawler_fallback(client):
    r = client.get("/")
    root_index = r.text.index('<div id="root"></div>')
    app_entry_index = r.text.index("/src/main.tsx")
    fallback_index = r.text.index('data-seo-shell="home"')

    assert root_index < fallback_index
    assert app_entry_index < fallback_index


def test_resume_seo_html_exposes_resume_in_app_shell(client):
    r = client.get("/resume")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert r.text.lower().startswith("<!doctype html>")
    assert '<div id="root">' in r.text
    assert 'data-seo-shell="resume"' in r.text
    assert 'type="module"' in r.text
    assert "站点加载中" not in r.text
    assert "Felix" in r.text
    assert "上海 / Remote" in r.text
    assert "felix@example.com" in r.text
    assert "/resume.md" in r.text
    assert "/api/v1/site/resume" in r.text
    assert "application/ld+json" in r.text
    assert "ProfilePage" in r.text
    assert "Person" in r.text


def test_resume_seo_html_uses_configured_real_name_in_browser_title(client):
    configure_search_identity(real_name="测试姓名", meta_title="测试搜索标题")

    r = client.get("/resume")
    assert r.status_code == 200
    assert "<title>测试姓名</title>" in r.text
    assert '<meta property="og:title" content="测试姓名 Resume · Aerisun">' in r.text
    assert '<meta name="author" content="测试姓名">' in r.text

    graph = read_json_ld_graph(r.text)
    profile_page = next(item for item in graph if item.get("@type") == "ProfilePage")
    person = next(item for item in graph if item.get("@type") == "Person")
    assert profile_page["name"] == "测试姓名 Resume"
    assert person["name"] == "测试姓名"
    assert "Aerisun" in person["alternateName"]


def test_content_collection_seo_html_exposes_public_entries_in_app_shell(client):
    cases = [
        ("/posts", "posts", "from-zero-design-system", "从零搭建个人设计系统的完整思路"),
        ("/diary", "diary", "spring-equinox-and-warm-light", "春分，天气转暖"),
        ("/thoughts", "thoughts", "spacing-rhythm-note", "排版节奏的一点记录"),
        ("/excerpts", "excerpts", "good-design-note", "关于留白的节选"),
    ]

    for path, shell_key, slug, title in cases:
        r = client.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert '<div id="root">' in r.text
        assert f'data-seo-shell="{shell_key}"' in r.text
        assert 'type="module"' in r.text
        assert title in r.text
        assert slug in r.text
        assert "站点加载中" not in r.text
        assert "ItemList" in r.text


def test_content_detail_seo_html_exposes_public_post_and_diary_in_app_shell(client):
    cases = [
        ("/posts/from-zero-design-system", "post-detail", "从零搭建个人设计系统的完整思路", "BlogPosting"),
        ("/diary/spring-equinox-and-warm-light", "diary-detail", "春分，天气转暖", "BlogPosting"),
    ]

    for path, shell_key, title, schema_type in cases:
        r = client.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert '<div id="root">' in r.text
        assert f'data-seo-shell="{shell_key}"' in r.text
        assert 'type="module"' in r.text
        assert title in r.text
        assert path in r.text
        assert schema_type in r.text
        assert "站点加载中" not in r.text


def test_social_seo_html_exposes_friends_and_guestbook_in_app_shell(client):
    cases = [
        ("/friends", "friends", "Arthals&#x27; ink", "Friend links"),
        ("/guestbook", "guestbook", "Elena Torres", "Guestbook entries"),
    ]

    for path, shell_key, visible_text, schema_name in cases:
        r = client.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert '<div id="root">' in r.text
        assert f'data-seo-shell="{shell_key}"' in r.text
        assert 'type="module"' in r.text
        assert visible_text in r.text
        assert schema_name in r.text
        assert "ItemList" in r.text
        assert "站点加载中" not in r.text


def test_seo_html_only_claims_explicit_static_entry_paths(client):
    assert client.get("/calendar").status_code == 404
