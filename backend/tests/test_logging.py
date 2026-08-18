from __future__ import annotations

from starlette.requests import Request

from aerisun.core.logging import _is_public_visit_candidate


def _request_for_path(path: str, *, method: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("203.0.113.44", 12345),
            "server": ("testserver", 80),
        }
    )


def test_request_id_header(client):
    """验证每个请求都返回 X-Request-ID 头。"""
    resp = client.get("/api/v1/site/healthz")
    assert resp.status_code == 200
    request_id = resp.headers.get("x-request-id")
    assert request_id is not None
    assert len(request_id) > 10  # UUID 格式


def test_request_id_unique(client):
    """验证不同请求的 ID 不同。"""
    resp1 = client.get("/api/v1/site/healthz")
    resp2 = client.get("/api/v1/site/healthz")
    id1 = resp1.headers.get("x-request-id")
    id2 = resp2.headers.get("x-request-id")
    assert id1 != id2


def test_public_visit_candidate_excludes_static_and_ai_entry_paths():
    for path in (
        "/manifest.webmanifest",
        "/favicon.ico",
        "/bootstrap.js",
        "/robots.txt",
        "/llms.txt",
        "/resume.md",
        "/sitemap.xml",
        "/feeds/articles.xml",
        "/assets/app.js",
        "/mcp/install",
        "/mcp/install/claude.sh",
    ):
        assert _is_public_visit_candidate(_request_for_path(path)) is False

    assert _is_public_visit_candidate(_request_for_path("/posts/hello-world")) is True
