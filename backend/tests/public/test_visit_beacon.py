"""Tests for the public page-view beacon endpoint."""

from __future__ import annotations

ENDPOINT = "/api/v1/site-interactions/visit"


def test_visit_beacon_accepts_payload(client):
    resp = client.post(
        ENDPOINT,
        json={
            "url": "/posts/123?utm_source=twitter",
            "referer": "https://www.google.com/",
            "screen": "1920x1080",
            "language": "zh-CN",
            "load_ms": 842,
        },
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"},
    )
    assert resp.status_code == 200
    assert "accepted" in resp.json()


def test_visit_beacon_accepts_oversized_load_ms(client):
    # An absurd load time must not reject the beacon; it is clamped server-side.
    resp = client.post(
        ENDPOINT,
        json={"url": "/", "load_ms": 10_000_000},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"},
    )
    assert resp.status_code == 200
    assert "accepted" in resp.json()


def test_visit_beacon_requires_url(client):
    resp = client.post(ENDPOINT, json={"referer": "https://example.com/"})
    assert resp.status_code == 422
