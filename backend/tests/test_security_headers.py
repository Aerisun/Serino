from __future__ import annotations


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


def test_no_hsts_in_development(client):
    response = client.get("/api/v1/site/healthz")
    assert "Strict-Transport-Security" not in response.headers
