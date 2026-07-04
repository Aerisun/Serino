from __future__ import annotations


def _csp_directives(csp: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for raw_directive in csp.split(";"):
        parts = raw_directive.strip().split()
        if not parts:
            continue
        directives[parts[0]] = parts[1:]
    return directives


def test_security_headers_present(client):
    response = client.get("/api/v1/site/healthz")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "Content-Security-Policy" in response.headers


def test_csp_includes_default_src(client):
    response = client.get("/api/v1/site/healthz")
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src" in csp
    assert "img-src" in csp


def test_csp_allows_frontend_bootstrap_inline_scripts(client):
    response = client.get("/api/v1/site/healthz")
    directives = _csp_directives(response.headers["Content-Security-Policy"])

    assert directives["script-src"][:2] == ["'self'", "'unsafe-inline'"]


def test_csp_allows_external_public_media(client):
    response = client.get("/api/v1/site/healthz")
    directives = _csp_directives(response.headers["Content-Security-Policy"])

    assert directives["media-src"] == ["'self'", "data:", "blob:", "https:"]


def test_no_hsts_in_development(client):
    response = client.get("/api/v1/site/healthz")
    assert "Strict-Transport-Security" not in response.headers
