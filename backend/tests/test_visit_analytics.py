"""Unit tests for visitor analytics enrichment helpers."""

from __future__ import annotations

from aerisun.domain.ops.user_agent import (
    DEVICE_BOT,
    DEVICE_DESKTOP,
    DEVICE_MOBILE,
    DEVICE_TABLET,
    parse_user_agent,
)
from aerisun.domain.ops.visit_tracking import (
    classify_visit_path,
    compute_visitor_id,
    is_trackable_page_visit_path,
    parse_referer,
    parse_utm,
    split_path_query,
)

UA_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
UA_WINDOWS_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.6099.130 Safari/537.36"
)
UA_IPAD = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
UA_GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


class TestParseUserAgent:
    def test_mobile_safari(self):
        info = parse_user_agent(UA_IPHONE)
        assert info.browser == "Mobile Safari"
        assert info.os == "iOS"
        assert info.device_type == DEVICE_MOBILE
        assert info.is_bot is False

    def test_desktop_chrome_with_versions(self):
        info = parse_user_agent(UA_WINDOWS_CHROME)
        assert info.browser == "Chrome"
        assert info.browser_version.startswith("120")
        assert info.os == "Windows"
        assert info.device_type == DEVICE_DESKTOP

    def test_tablet(self):
        info = parse_user_agent(UA_IPAD)
        assert info.device_type == DEVICE_TABLET

    def test_bot_detection(self):
        info = parse_user_agent(UA_GOOGLEBOT)
        assert info.is_bot is True
        assert info.device_type == DEVICE_BOT

    def test_curl_is_bot(self):
        info = parse_user_agent("curl/8.4.0")
        assert info.is_bot is True

    def test_empty(self):
        info = parse_user_agent(None)
        assert info.browser is None
        assert info.device_type == "unknown"
        assert info.is_bot is False


class TestVisitTracking:
    def test_split_path_query_strips_fragment(self):
        path, query = split_path_query("/posts/123?utm_source=x&a=b#frag")
        assert path == "/posts/123"
        assert query == "utm_source=x&a=b"

    def test_split_path_query_defaults(self):
        assert split_path_query(None) == ("/", None)
        assert split_path_query("posts") == ("/posts", None)

    def test_parse_referer_external(self):
        assert parse_referer("https://www.google.com/search?q=x", current_host="blog.com") == "google.com"

    def test_parse_referer_drops_same_host(self):
        assert parse_referer("https://blog.com/posts", current_host="blog.com") is None
        assert parse_referer("https://www.blog.com/x", current_host="blog.com") is None

    def test_parse_referer_empty(self):
        assert parse_referer(None) is None
        assert parse_referer("not a url") is None

    def test_parse_utm(self):
        utm = parse_utm("utm_source=twitter&utm_medium=social&utm_campaign=launch")
        assert utm.source == "twitter"
        assert utm.medium == "social"
        assert utm.campaign == "launch"
        assert utm.term is None

    def test_parse_utm_empty(self):
        utm = parse_utm(None)
        assert utm.source is None

    def test_visitor_id_is_stable_and_anonymous(self):
        first = compute_visitor_id("1.2.3.4", "UA")
        second = compute_visitor_id("1.2.3.4", "UA")
        other = compute_visitor_id("5.6.7.8", "UA")
        assert first == second
        assert first != other
        # The raw IP must not be recoverable from the hash.
        assert "1.2.3.4" not in first
        assert len(first) == 32

    def test_classifies_static_system_resources_outside_page_views(self):
        for path in (
            "/manifest.webmanifest",
            "/manifest.webmanifest/",
            "/favicon",
            "/favicon.ico",
            "/bootstrap.js",
            "/robots.txt",
            "/sitemap.xml",
            "/assets/",
            "/assets/app.js",
            "/assets/icons/site.webmanifest",
            "/mcp/install",
            "/mcp/install/codex.sh",
            "/mcp/install/claude-marketplace.json",
        ):
            assert classify_visit_path(path) == "system_resource"
            assert is_trackable_page_visit_path(path) is False

    def test_classifies_ai_and_crawler_entry_paths_outside_page_views(self):
        for path in (
            "/llms.txt",
            "/resume.md",
            "/feed.xml",
            "/rss.xml",
            "/feeds.xml",
            "/feeds/",
            "/feeds/articles.xml",
            "/feeds/thoughts.xml",
        ):
            assert classify_visit_path(path) == "ai_entry"
            assert is_trackable_page_visit_path(path) is False

    def test_keeps_real_public_pages_trackable(self):
        for path in ("/", "/posts/hello-world", "/resume", "/thoughts?utm_source=feed"):
            assert classify_visit_path(path) == "page"
            assert is_trackable_page_visit_path(path) is True


class TestClampLoadMs:
    def test_none_becomes_zero(self):
        from aerisun.domain.ops.service import _clamp_load_ms

        assert _clamp_load_ms(None) == 0

    def test_negative_clamped_to_zero(self):
        from aerisun.domain.ops.service import _clamp_load_ms

        assert _clamp_load_ms(-50) == 0

    def test_oversized_clamped_to_max(self):
        from aerisun.domain.ops.service import _BEACON_MAX_LOAD_MS, _clamp_load_ms

        assert _clamp_load_ms(10_000_000) == _BEACON_MAX_LOAD_MS

    def test_normal_value_kept(self):
        from aerisun.domain.ops.service import _clamp_load_ms

        assert _clamp_load_ms(842) == 842
