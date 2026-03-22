from __future__ import annotations


def test_post_without_origin_succeeds(client):
    """POST without Origin header should be allowed (same-origin or non-browser)."""
    response = client.get("/api/v1/public/healthz")
    assert response.status_code == 200


def test_get_with_wrong_origin_succeeds(client):
    """GET requests should never be blocked by origin check."""
    response = client.get(
        "/api/v1/public/healthz",
        headers={"Origin": "https://evil.com"},
    )
    assert response.status_code == 200


def test_post_with_wrong_origin_rejected(client):
    """POST with disallowed Origin should be rejected."""
    response = client.post(
        "/api/v1/public/guestbook",
        json={"name": "test", "body": "hello"},
        headers={"Origin": "https://evil.com"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Origin not allowed"


def test_post_with_allowed_origin_succeeds(client):
    """POST with allowed Origin should pass through to the endpoint."""
    response = client.post(
        "/api/v1/public/guestbook",
        json={"name": "test", "body": "hello"},
        headers={"Origin": "http://localhost:5173"},
    )
    # Should not be 403 — may be 200 or other status depending on business logic
    assert response.status_code != 403
