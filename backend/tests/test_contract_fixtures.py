"""Export API response fixtures for contract testing.

Runs against a test FastAPI client (in-memory SQLite) and writes
response JSON to ``packages/api-client/src/__tests__/fixtures/`` so that the frontend
Zod-based contract tests can validate schema compatibility.

Usage (from repo root):
    cd backend && uv run pytest tests/test_contract_fixtures.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "packages" / "api-client" / "src" / "__tests__" / "fixtures"


def _write_fixture(name: str, data: dict | list) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    dest = FIXTURES_DIR / f"{name}.json"
    dest.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------

class TestPublicFixtures:
    def test_site_config(self, client):
        resp = client.get("/api/v1/public/site")
        assert resp.status_code == 200
        _write_fixture("public_site_config", resp.json())

    def test_pages(self, client):
        resp = client.get("/api/v1/public/pages")
        assert resp.status_code == 200
        _write_fixture("public_pages", resp.json())

    def test_posts_list(self, client):
        resp = client.get("/api/v1/public/posts")
        assert resp.status_code == 200
        _write_fixture("public_posts_list", resp.json())

    def test_healthz(self, client):
        resp = client.get("/api/v1/public/healthz")
        assert resp.status_code == 200
        _write_fixture("public_healthz", resp.json())


# ---------------------------------------------------------------------------
# Admin endpoints (auth required)
# ---------------------------------------------------------------------------

class TestAdminFixtures:
    def test_admin_me(self, client, admin_headers):
        resp = client.get("/api/v1/admin/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        _write_fixture("admin_me", resp.json())

    def test_admin_posts_list(self, client, admin_headers):
        resp = client.get("/api/v1/admin/posts/", headers=admin_headers)
        assert resp.status_code == 200
        _write_fixture("admin_posts_list", resp.json())

    def test_admin_sessions(self, client, admin_headers):
        resp = client.get("/api/v1/admin/auth/sessions", headers=admin_headers)
        assert resp.status_code == 200
        _write_fixture("admin_sessions", resp.json())
