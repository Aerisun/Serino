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
from uuid import NAMESPACE_URL, UUID, uuid5

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "packages" / "api-client" / "src" / "__tests__" / "fixtures"
)
FIXTURE_TIMESTAMP_KEYS = {"created_at", "updated_at", "expires_at", "timestamp"}
FIXTURE_TIMESTAMP_VALUES = {
    "expires_at": "2026-01-02T00:00:00+08:00",
}
FIXTURE_DEFAULT_TIMESTAMP = "2026-01-01T00:00:00+08:00"


def _stable_fixture_uuid(path: tuple[str, ...]) -> str:
    return str(uuid5(NAMESPACE_URL, "aerisun-contract-fixture:" + ".".join(path)))


def _is_uuid_like(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _normalize_fixture_data(data: dict | list | str | int | float | bool | None, path: tuple[str, ...] = ()):
    if isinstance(data, list):
        return [_normalize_fixture_data(item, (*path, str(index))) for index, item in enumerate(data)]
    if isinstance(data, dict):
        return {key: _normalize_fixture_value(key, value, (*path, key)) for key, value in data.items()}
    return data


def _normalize_fixture_value(key: str, value, path: tuple[str, ...]):
    if isinstance(value, str) and _is_uuid_like(value):
        return _stable_fixture_uuid(path)
    if key in FIXTURE_TIMESTAMP_KEYS and isinstance(value, str):
        return FIXTURE_TIMESTAMP_VALUES.get(key, FIXTURE_DEFAULT_TIMESTAMP)
    return _normalize_fixture_data(value, path)


def _write_fixture(name: str, data: dict | list) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    dest = FIXTURES_DIR / f"{name}.json"
    normalized = _normalize_fixture_data(data)
    dest.write_text(json.dumps(normalized, indent=2, default=str, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------


class TestPublicFixtures:
    def test_site_config(self, client):
        resp = client.get("/api/v1/site/site")
        assert resp.status_code == 200
        _write_fixture("public_site_config", resp.json())

    def test_pages(self, client):
        resp = client.get("/api/v1/site/pages")
        assert resp.status_code == 200
        _write_fixture("public_pages", resp.json())

    def test_posts_list(self, client):
        resp = client.get("/api/v1/site/posts")
        assert resp.status_code == 200
        _write_fixture("public_posts_list", resp.json())

    def test_healthz(self, client):
        resp = client.get("/api/v1/site/healthz")
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
