from __future__ import annotations

import json
import re

from aerisun.core.db import get_session_factory
from aerisun.domain.content.seo_service import build_robots_txt
from aerisun.domain.diary_access.service import DIARY_PRIVATE_FEATURE_FLAG
from aerisun.domain.site_config.models import ResumeBasics, SiteProfile


def configure_search_identity(*, homepage_name: str | None = None, **search_optimization: str) -> None:
    factory = get_session_factory()
    with factory() as session:
        profile = session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
        assert profile is not None
        if homepage_name is not None:
            profile.name = homepage_name
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            "search_optimization": search_optimization,
        }
        session.commit()


def configure_diary_private(enabled: bool) -> None:
    factory = get_session_factory()
    with factory() as session:
        profile = session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
        assert profile is not None
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            DIARY_PRIVATE_FEATURE_FLAG: enabled,
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


def test_robots_txt_allows_discovery_without_overblocking_general_crawlers(client):
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
        assert f"User-agent: {user_agent}\nDisallow: /" not in r.text
        assert f"User-agent: {user_agent}" not in r.text


def test_robots_txt_uses_configured_admin_base_path():
    content = build_robots_txt(
        "https://example.com",
        admin_base_path="/control-room/",
        api_base_path="/api",
    )

    assert "Disallow: /control-room/" in content
    assert "Disallow: /admin/" not in content


def test_robots_and_feeds_use_the_configured_canonical_site_root(client):
    configure_search_identity(canonical_url="HTTPS://CANONICAL.EXAMPLE:443/")

    robots = client.get("/robots.txt")
    feed = client.get("/feeds/posts.xml")

    assert robots.status_code == 200
    assert "Sitemap: https://canonical.example/sitemap.xml" in robots.text
    assert feed.status_code == 200
    assert "https://canonical.example/feeds/posts.xml" in feed.text
    assert "https://canonical.example/posts/from-zero-design-system" in feed.text


def test_canonical_configuration_with_a_path_falls_back_to_the_deployment_origin(client):
    configure_search_identity(canonical_url="https://canonical.example/blog")

    robots = client.get("/robots.txt")

    assert robots.status_code == 200
    assert "Sitemap: http://localhost:8080/sitemap.xml" in robots.text


def test_llms_txt_guides_ai_agents_to_person_and_public_content(client):
    configure_diary_private(False)
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
    assert (
        "For public writing, read /posts and /diary first; they are crawler-readable index pages with summaries and canonical links."
        in r.text
    )
    assert (
        "Strongly recommended: open every public /posts/{slug} and /diary/{slug} detail page in the order shown on /posts and /diary before summarizing the person's writing."
        in r.text
    )
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
    configure_diary_private(False)
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
    assert (
        "AI agents and search assistants must fetch and read http://localhost:8080/llms.txt first before summarizing this person, answering questions about this site, or crawling public content."
        in r.text
    )
    assert "/feeds/posts.xml" in r.text
    assert "/feeds/diary.xml" in r.text
    assert "/posts" in r.text
    for href in ("/", "/resume", "/posts", "/diary"):
        assert f'href="http://localhost:8080{href}"' in r.text
    assert "AI-readable homepage" not in r.text
    assert "AI-readable resume page" not in r.text
    assert '<a href="http://localhost:8080/diary">Diary</a>' in r.text
    assert 'href="http://localhost:8080/feeds/diary.xml" title="Latest public diary entries"' in r.text
    assert "application/ld+json" in r.text
    assert "WebSite" in r.text
    assert "Person" in r.text
    assert "<title>Felix</title>" in r.text
    assert "This is the personal website, blog, and public work archive for Felix (Aerisun)." not in r.text


def test_identity_name_uses_site_profile_and_image_uses_resume_profile(client):
    factory = get_session_factory()
    with factory() as session:
        profile = session.query(SiteProfile).one()
        profile.name = "Public Brand"
        profile.og_image = "/media/public-brand.webp"
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            "search_optimization": {},
        }
        resume = session.query(ResumeBasics).one()
        resume.title = "Different Resume Name"
        resume.profile_image_url = "/media/resume-only.webp"
        session.commit()

    response = client.get("/")
    graph = read_json_ld_graph(response.text)
    person = next(item for item in graph if item.get("@type") == "Person")

    assert person["name"] == "Public Brand"
    assert person["image"] == "http://localhost:8080/media/resume-only.webp"
    assert '<meta property="og:image" content="http://localhost:8080/media/resume-only.webp">' in response.text


def test_identity_image_falls_back_to_hero_then_homepage_static_image(client):
    factory = get_session_factory()
    with factory() as session:
        profile = session.query(SiteProfile).one()
        profile.hero_image_url = "/media/hero.webp"
        profile.og_image = "/media/homepage-static.webp"
        resume = session.query(ResumeBasics).one()
        resume.profile_image_url = ""
        session.commit()

    hero_response = client.get("/")
    assert '<meta property="og:image" content="http://localhost:8080/media/hero.webp">' in hero_response.text

    with factory() as session:
        profile = session.query(SiteProfile).one()
        profile.hero_image_url = ""
        session.commit()

    static_response = client.get("/")
    assert (
        '<meta property="og:image" content="http://localhost:8080/media/homepage-static.webp">' in static_response.text
    )


def test_home_seo_html_falls_back_to_homepage_name_when_bilingual_identity_is_incomplete(client):
    configure_search_identity(
        homepage_name="Aerisun",
        real_name="测试姓名",
        meta_title="测试搜索标题",
        meta_description="用户填写的测试摘要",
    )

    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Aerisun</title>" in r.text
    assert '<meta property="og:title" content="测试搜索标题">' in r.text
    assert '<meta name="author" content="测试姓名">' in r.text
    assert '<meta name="description" content="用户填写的测试摘要">' in r.text

    graph = read_json_ld_graph(r.text)
    person = next(item for item in graph if item.get("@type") == "Person")
    website = next(item for item in graph if item.get("@type") == "WebSite")
    assert person["name"] == "测试姓名"
    assert "Aerisun" in person["alternateName"]
    assert website["about"] == {"@id": "http://localhost:8080/#person"}
    assert website["mainEntity"] == {"@id": "http://localhost:8080/#person"}


def test_home_seo_html_does_not_pair_english_name_with_a_fallback_real_name(client):
    configure_search_identity(homepage_name="Aerisun", english_name="Wenbo Yang")

    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Aerisun</title>" in r.text
    assert "<title>Aerisun - Felix(Wenbo Yang)</title>" not in r.text


def test_home_seo_description_uses_the_configured_text_without_identity_prefixes(client):
    configured_description = "杨汶帛，北京大学集成电路设计与集成系统专业24级本科生，辅修智能科学与技术"
    configure_search_identity(
        homepage_name="Aerisun",
        real_name="杨汶帛",
        english_name="Wenbo Yang",
        meta_description=configured_description,
    )

    r = client.get("/")
    assert r.status_code == 200
    assert f'<meta name="description" content="{configured_description}">' in r.text


def test_home_seo_description_preserves_internal_spacing_newlines_and_length(client):
    configured_description = "杨汶帛  Wenbo Yang\n" + ("北京大学集成电路设计与集成系统专业本科生。" * 20)
    configure_search_identity(
        homepage_name="Aerisun",
        real_name="杨汶帛",
        english_name="Wenbo Yang",
        meta_description=f"  {configured_description}  ",
    )

    r = client.get("/")
    assert r.status_code == 200
    assert f'<meta name="description" content="{configured_description}">' in r.text
    graph = read_json_ld_graph(r.text)
    person = next(item for item in graph if item.get("@type") == "Person")
    website = next(item for item in graph if item.get("@type") == "WebSite")
    assert person["description"] == configured_description
    assert website["description"] == configured_description


def test_unsafe_canonical_configuration_falls_back_to_the_deployment_url(client):
    configure_search_identity(canonical_url="javascript:alert(1)")

    r = client.get("/")

    assert r.status_code == 200
    assert '<link rel="canonical" href="http://localhost:8080/">' in r.text
    assert "javascript:alert" not in r.text


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
    assert '<meta property="og:title" content="测试姓名 Resume · Felix">' in r.text
    assert '<meta name="author" content="测试姓名">' in r.text

    graph = read_json_ld_graph(r.text)
    profile_page = next(item for item in graph if item.get("@type") == "ProfilePage")
    person = next(item for item in graph if item.get("@type") == "Person")
    assert profile_page["name"] == "测试姓名 Resume"
    assert person["name"] == "测试姓名"
    assert "Felix" in person["alternateName"]


def test_bilingual_search_identity_is_consistent_across_public_crawler_surfaces(client):
    configure_search_identity(
        homepage_name="Aerisun",
        real_name="杨汶帛",
        english_name="Wenbo Yang",
        meta_title="杨汶帛 - 北京大学24级本科生",
        canonical_url="https://aerisun.top",
    )

    home = client.get("/")
    assert home.status_code == 200
    assert "<title>Aerisun - 杨汶帛(Wenbo Yang)</title>" in home.text
    assert "杨汶帛" in home.text
    assert "Wenbo Yang" in home.text
    assert ">杨汶帛 - Wenbo Yang</a>" in home.text

    home_graph = read_json_ld_graph(home.text)
    person = next(item for item in home_graph if item.get("@type") == "Person")
    website = next(item for item in home_graph if item.get("@type") == "WebSite")
    assert person["name"] == "杨汶帛"
    assert person["alternateName"] == ["Wenbo Yang", "Aerisun"]
    assert website["name"] == "Aerisun"
    assert '<meta name="keywords" content="杨汶帛, Wenbo Yang, Aerisun">' in home.text

    resume = client.get("/resume")
    assert resume.status_code == 200
    assert "<title>杨汶帛 - Wenbo Yang</title>" in resume.text
    assert "<h1>杨汶帛 - Wenbo Yang</h1>" in resume.text
    assert 'content="杨汶帛 - Wenbo Yang Resume · Aerisun"' in resume.text

    posts = client.get("/posts")
    assert posts.status_code == 200
    assert "<title>Posts · Aerisun</title>" in posts.text
    assert "<title>Posts · Aerisun - 杨汶帛(Wenbo Yang)</title>" not in posts.text

    article = client.get("/posts/from-zero-design-system")
    assert article.status_code == 200
    assert (
        '"author":{"@type":"Person","@id":"https://aerisun.top/#person","name":"杨汶帛","url":"https://aerisun.top/resume"}'
        in article.text
    )
    article_json_ld_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', article.text)
    assert article_json_ld_match is not None
    article_json_ld = json.loads(article_json_ld_match.group(1))
    assert article_json_ld["publisher"] == {"@id": "https://aerisun.top/#person"}
    assert '<meta name="keywords" content="杨汶帛, Wenbo Yang, Aerisun' in article.text
    assert '<meta name="title"' not in article.text

    resume_markdown = client.get("/resume.md")
    assert resume_markdown.status_code == 200
    assert resume_markdown.text.startswith("# 杨汶帛 - Wenbo Yang")

    llms = client.get("/llms.txt")
    assert llms.status_code == 200
    assert llms.text.startswith("# 杨汶帛 - Wenbo Yang")
    assert "杨汶帛" in llms.text
    assert "Wenbo Yang" in llms.text
    assert "Aerisun" in llms.text
    assert "Wenbo Yang and Aerisun are public alternate names for 杨汶帛." in llms.text


def test_protected_posts_never_leak_into_public_crawler_surfaces(client, admin_headers):
    secret_body = "approval-only-secret-body-7d9f"
    created = client.post(
        "/api/v1/admin/posts/",
        json={
            "slug": "approval-only-crawler-secret",
            "title": "Approval Only Crawler Secret",
            "body": secret_body,
            "visibility": "public",
            "requires_approval": True,
        },
        headers=admin_headers,
    )
    assert created.status_code == 201

    detail = client.get("/posts/approval-only-crawler-secret")
    posts = client.get("/posts")
    home = client.get("/")
    sitemap = client.get("/sitemap.xml")
    feed = client.get("/feeds/posts.xml")
    llms = client.get("/llms.txt")

    assert detail.status_code == 404
    for response in (detail, posts, home, sitemap, feed, llms):
        assert secret_body not in response.text
    for response in (posts, home, sitemap, feed, llms):
        assert "approval-only-crawler-secret" not in response.text


def test_person_same_as_only_contains_http_identity_pages(client):
    configure_search_identity(
        real_name="杨汶帛",
        english_name="Wenbo Yang",
        same_as="https://github.com/Aerisun\nmailto:ywb@example.com",
    )

    r = client.get("/")
    assert r.status_code == 200
    graph = read_json_ld_graph(r.text)
    person = next(item for item in graph if item.get("@type") == "Person")
    assert "https://github.com/Aerisun" in person["sameAs"]
    assert all(str(link).startswith(("http://", "https://")) for link in person["sameAs"])


def test_content_collection_seo_html_exposes_public_entries_in_app_shell(client):
    configure_diary_private(False)
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
    configure_diary_private(False)
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
