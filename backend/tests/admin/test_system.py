"""Integration tests for admin system endpoints.

Covers dashboard stats, system info, audit logs, API key management,
and backup endpoints exposed under ``/api/v1/admin/system/``.
"""

from __future__ import annotations

BASE = "/api/v1/admin/system"


# ── Dashboard Stats ───────────────────────────────────────────────────


class TestDashboardStats:

    def test_dashboard_stats_returns_counts(self, client, admin_headers):
        resp = client.get(f"{BASE}/dashboard/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # All expected top-level count keys are present
        for key in (
            "posts",
            "diary_entries",
            "thoughts",
            "excerpts",
            "comments",
            "guestbook_entries",
            "friends",
            "assets",
        ):
            assert key in data
            assert isinstance(data[key], int)
        # Enhanced fields
        assert "posts_by_status" in data
        assert "content_by_month" in data
        assert "recent_content" in data

    def test_dashboard_stats_without_token(self, client):
        resp = client.get(f"{BASE}/dashboard/stats")
        assert resp.status_code in (401, 403)


# ── System Info ───────────────────────────────────────────────────────


class TestSystemInfo:

    def test_system_info(self, client, admin_headers):
        resp = client.get(f"{BASE}/info", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "python_version" in data
        assert "db_size_bytes" in data
        assert "media_dir_size_bytes" in data
        assert "uptime_seconds" in data
        assert "environment" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_system_info_without_token(self, client):
        resp = client.get(f"{BASE}/info")
        assert resp.status_code in (401, 403)


# ── Audit Logs ────────────────────────────────────────────────────────


class TestAuditLogs:

    def test_list_audit_logs(self, client, admin_headers):
        resp = client.get(f"{BASE}/audit-logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)

    def test_audit_logs_pagination(self, client, admin_headers):
        resp = client.get(
            f"{BASE}/audit-logs",
            params={"page": 1, "page_size": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_audit_logs_without_token(self, client):
        resp = client.get(f"{BASE}/audit-logs")
        assert resp.status_code in (401, 403)


# ── API Key Management ────────────────────────────────────────────────


class TestApiKeys:

    def test_api_key_lifecycle(self, client, admin_headers):
        # CREATE
        resp = client.post(
            f"{BASE}/api-keys",
            json={"key_name": "test-key", "scopes": ["read"]},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "raw_key" in data
        assert data["item"]["key_name"] == "test-key"
        assert data["item"]["scopes"] == ["read"]
        key_id = data["item"]["id"]

        # LIST
        resp = client.get(f"{BASE}/api-keys", headers=admin_headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert any(k["id"] == key_id for k in keys)

        # UPDATE
        resp = client.put(
            f"{BASE}/api-keys/{key_id}",
            json={"key_name": "renamed-key"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["key_name"] == "renamed-key"

        # DELETE
        resp = client.delete(
            f"{BASE}/api-keys/{key_id}", headers=admin_headers
        )
        assert resp.status_code == 204

        # Verify gone
        resp = client.get(f"{BASE}/api-keys", headers=admin_headers)
        assert not any(k["id"] == key_id for k in resp.json())

    def test_delete_nonexistent_api_key(self, client, admin_headers):
        resp = client.delete(
            f"{BASE}/api-keys/nonexistent-key-id", headers=admin_headers
        )
        assert resp.status_code == 404

    def test_api_keys_without_token(self, client):
        resp = client.get(f"{BASE}/api-keys")
        assert resp.status_code in (401, 403)


# ── Backups ───────────────────────────────────────────────────────────


class TestBackups:

    def test_backup_lifecycle(self, client, admin_headers):
        # LIST (initially empty)
        resp = client.get(f"{BASE}/backups", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        # TRIGGER
        resp = client.post(f"{BASE}/backups", headers=admin_headers)
        assert resp.status_code == 201
        snapshot = resp.json()
        assert snapshot["snapshot_type"] == "manual"
        assert snapshot["status"] == "queued"
        snapshot_id = snapshot["id"]

        # LIST again — should contain the new snapshot
        resp = client.get(f"{BASE}/backups", headers=admin_headers)
        assert any(s["id"] == snapshot_id for s in resp.json())

        # RESTORE
        resp = client.post(
            f"{BASE}/backups/{snapshot_id}/restore", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "restoring"

    def test_restore_nonexistent_backup(self, client, admin_headers):
        resp = client.post(
            f"{BASE}/backups/nonexistent-id/restore", headers=admin_headers
        )
        assert resp.status_code == 404

    def test_backups_without_token(self, client):
        resp = client.get(f"{BASE}/backups")
        assert resp.status_code in (401, 403)
