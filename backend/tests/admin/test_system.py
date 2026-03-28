"""Integration tests for admin system endpoints.

Covers dashboard stats, system info, audit logs, API key management,
and backup endpoints exposed under ``/api/v1/admin/system/``.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.ops.models import TrafficDailySnapshot, VisitRecord
from aerisun.domain.waline.service import set_counter_value

BASE = "/api/v1/admin/system"


def _reset_waline_counters() -> None:
    waline_db_path = get_settings().waline_db_path
    connection = sqlite3.connect(waline_db_path)
    try:
        connection.execute("DELETE FROM wl_counter")
        connection.commit()
    finally:
        connection.close()

    factory = get_session_factory()
    with factory() as session:
        session.query(TrafficDailySnapshot).delete()
        session.commit()


# ── Dashboard Stats ───────────────────────────────────────────────────


class TestDashboardStats:
    def test_dashboard_stats_returns_counts(self, client, admin_headers):
        _reset_waline_counters()
        resp = client.get(f"{BASE}/dashboard/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
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
        assert "posts_by_status" in data
        assert "content_by_month" in data
        assert "recent_content" in data
        assert "traffic" in data
        assert "visitors" in data
        assert "aux_metrics" in data

        visitors = data["visitors"]
        for key in (
            "total_visits",
            "unique_visitors_24h",
            "unique_visitors_7d",
            "average_request_duration_ms",
            "top_pages",
            "history",
            "recent_visits",
            "last_visit_at",
        ):
            assert key in visitors

    def test_dashboard_stats_returns_traffic_analytics(self, client, admin_headers):
        _reset_waline_counters()
        set_counter_value(url="/posts/alpha", pageview_count=120, reaction_counts={0: 8})
        set_counter_value(url="/posts/beta", pageview_count=45, reaction_counts={0: 3})
        set_counter_value(url="/diary/day-one", pageview_count=30)
        set_counter_value(url="/guestbook", pageview_count=999)

        factory = get_session_factory()
        today = datetime.now(UTC).date()
        with factory() as session:
            session.add_all(
                [
                    TrafficDailySnapshot(
                        snapshot_date=today - timedelta(days=2),
                        url="/posts/alpha",
                        cumulative_views=80,
                        daily_views=20,
                        cumulative_reactions=5,
                    ),
                    TrafficDailySnapshot(
                        snapshot_date=today - timedelta(days=1),
                        url="/posts/alpha",
                        cumulative_views=100,
                        daily_views=20,
                        cumulative_reactions=6,
                    ),
                    TrafficDailySnapshot(
                        snapshot_date=today - timedelta(days=1),
                        url="/posts/beta",
                        cumulative_views=30,
                        daily_views=10,
                        cumulative_reactions=2,
                    ),
                ]
            )
            session.commit()

        resp = client.get(f"{BASE}/dashboard/stats", headers=admin_headers)
        assert resp.status_code == 200
        payload = resp.json()

        traffic = payload["traffic"]
        assert traffic["total_views"] == 1194
        assert traffic["top_pages"][0]["url"] == "/posts/alpha"
        assert traffic["top_pages"][0]["views"] == 120
        assert traffic["top_pages"][1]["url"] == "/posts/beta"
        assert all(item["url"] != "/guestbook" for item in traffic["top_pages"])
        assert len(traffic["history"]) == 14
        history_by_date = {item["date"]: item["views"] for item in traffic["history"]}
        assert history_by_date[str(today - timedelta(days=2))] == 20
        assert history_by_date[str(today - timedelta(days=1))] == 30
        assert history_by_date[str(today)] == 1064
        assert traffic["last_snapshot_at"] is not None

        aux = payload["aux_metrics"]
        assert aux["pending_moderation"] >= 0
        assert aux["published_posts"] >= 0
        assert aux["published_diary_entries"] >= 0
        assert aux["published_thoughts"] >= 0
        assert aux["published_excerpts"] >= 0

    def test_dashboard_stats_returns_visitor_analytics(self, client, admin_headers):
        factory = get_session_factory()
        now = datetime.now(UTC)
        with factory() as session:
            session.add_all(
                [
                    VisitRecord(
                        visited_at=now - timedelta(hours=1),
                        path="/posts/hello",
                        ip_address="203.0.113.1",
                        user_agent="Mozilla/5.0",
                        referer="https://example.com",
                        status_code=200,
                        duration_ms=120,
                        is_bot=False,
                    ),
                    VisitRecord(
                        visited_at=now - timedelta(hours=2),
                        path="/posts/hello",
                        ip_address="203.0.113.2",
                        user_agent="Mozilla/5.0",
                        referer=None,
                        status_code=200,
                        duration_ms=80,
                        is_bot=False,
                    ),
                    VisitRecord(
                        visited_at=now - timedelta(days=2),
                        path="/diary/day-one",
                        ip_address="203.0.113.1",
                        user_agent="Mozilla/5.0",
                        referer=None,
                        status_code=200,
                        duration_ms=60,
                        is_bot=False,
                    ),
                ]
            )
            session.commit()

        resp = client.get(f"{BASE}/dashboard/stats", headers=admin_headers)
        assert resp.status_code == 200
        payload = resp.json()["visitors"]
        assert payload["total_visits"] >= 3
        assert payload["unique_visitors_24h"] >= 2
        assert payload["unique_visitors_7d"] >= 2
        assert payload["average_request_duration_ms"] >= 0
        assert len(payload["history"]) == 14
        assert any(item["url"] == "/posts/hello" for item in payload["top_pages"])
        assert len(payload["recent_visits"]) >= 3
        assert "status_text" in payload["recent_visits"][0]
        assert "location" in payload["recent_visits"][0]
        assert payload["last_visit_at"] is not None

    def test_list_visitor_records(self, client, admin_headers):
        factory = get_session_factory()
        now = datetime.now(UTC)
        with factory() as session:
            session.add(
                VisitRecord(
                    visited_at=now,
                    path="/thoughts/one",
                    ip_address="198.51.100.9",
                    user_agent="Mozilla/5.0",
                    referer=None,
                    status_code=200,
                    duration_ms=42,
                    is_bot=False,
                )
            )
            session.commit()

        resp = client.get(f"{BASE}/visitor-records", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert isinstance(data["items"], list)
        assert data["items"][0]["path"]
        assert "ip_address" in data["items"][0]
        assert "duration_ms" in data["items"][0]
        assert "status_text" in data["items"][0]
        assert "location" in data["items"][0]

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
        resp = client.post(
            f"{BASE}/api-keys",
            json={"key_name": "test-key", "scopes": ["content:read"]},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "raw_key" in data
        assert data["item"]["key_name"] == "test-key"
        assert data["item"]["scopes"] == ["content:read"]
        assert len(data["item"]["key_prefix"]) == 4
        assert len(data["item"]["key_suffix"]) == 3
        key_id = data["item"]["id"]

        resp = client.get(f"{BASE}/api-keys", headers=admin_headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert any(k["id"] == key_id for k in keys)

        resp = client.put(
            f"{BASE}/api-keys/{key_id}",
            json={"key_name": "renamed-key"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["key_name"] == "renamed-key"

        resp = client.delete(f"{BASE}/api-keys/{key_id}", headers=admin_headers)
        assert resp.status_code == 204

        resp = client.get(f"{BASE}/api-keys", headers=admin_headers)
        assert not any(k["id"] == key_id for k in resp.json())

    def test_delete_nonexistent_api_key(self, client, admin_headers):
        resp = client.delete(f"{BASE}/api-keys/nonexistent-key-id", headers=admin_headers)
        assert resp.status_code == 404

    def test_api_keys_without_token(self, client):
        resp = client.get(f"{BASE}/api-keys")
        assert resp.status_code in (401, 403)


# ── Backups ───────────────────────────────────────────────────────────


class TestBackups:
    def test_backup_lifecycle(self, client, admin_headers):
        resp = client.get(f"{BASE}/backups", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        resp = client.post(f"{BASE}/backups", headers=admin_headers)
        assert resp.status_code == 201
        snapshot = resp.json()
        assert snapshot["snapshot_type"] == "manual"
        assert snapshot["status"] == "queued"
        snapshot_id = snapshot["id"]

        resp = client.get(f"{BASE}/backups", headers=admin_headers)
        assert any(s["id"] == snapshot_id for s in resp.json())

        resp = client.post(f"{BASE}/backups/{snapshot_id}/restore", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "restoring"

    def test_restore_nonexistent_backup(self, client, admin_headers):
        resp = client.post(f"{BASE}/backups/nonexistent-id/restore", headers=admin_headers)
        assert resp.status_code == 404

    def test_backups_without_token(self, client):
        resp = client.get(f"{BASE}/backups")
        assert resp.status_code in (401, 403)
