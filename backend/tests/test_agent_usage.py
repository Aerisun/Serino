from __future__ import annotations

from aerisun.api.admin.scopes import (
    AGENT_CONNECT,
    ASSETS_READ,
    ASSETS_WRITE,
    AUTH_READ,
    AUTH_WRITE,
    AUTOMATION_READ,
    AUTOMATION_WRITE,
    CONFIG_READ,
    CONFIG_WRITE,
    CONTENT_READ,
    CONTENT_WRITE,
    MODERATION_READ,
    MODERATION_WRITE,
    NETWORK_READ,
    NETWORK_WRITE,
    SUBSCRIPTIONS_READ,
    SUBSCRIPTIONS_WRITE,
    SYSTEM_READ,
    SYSTEM_WRITE,
    VISITORS_READ,
    VISITORS_WRITE,
)
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.agent.service import build_workflow_planning_usage_context
from aerisun.domain.iam.models import ApiKey

READONLY_PRESET_SCOPES = [
    AGENT_CONNECT,
    CONTENT_READ,
    MODERATION_READ,
    CONFIG_READ,
    ASSETS_READ,
    SUBSCRIPTIONS_READ,
    VISITORS_READ,
    AUTH_READ,
    AUTOMATION_READ,
    SYSTEM_READ,
    NETWORK_READ,
]

BASIC_MANAGEMENT_PRESET_SCOPES = [
    *READONLY_PRESET_SCOPES,
    CONTENT_WRITE,
    MODERATION_WRITE,
]

FULL_MANAGEMENT_PRESET_SCOPES = [
    *BASIC_MANAGEMENT_PRESET_SCOPES,
    CONFIG_WRITE,
    ASSETS_WRITE,
    SUBSCRIPTIONS_WRITE,
    VISITORS_WRITE,
    AUTH_WRITE,
    AUTOMATION_WRITE,
    SYSTEM_WRITE,
    NETWORK_WRITE,
]


class TestAgentUsage:
    def _enable_mcp(self, client, admin_headers):
        response = client.put(
            "/api/v1/admin/integrations/mcp-config",
            json={"public_access": True},
            headers=admin_headers,
        )
        assert response.status_code == 200
        return response.json()

    def _create_key(self, client, admin_headers, name: str, scopes: list[str]) -> tuple[str, str]:
        response = client.post(
            "/api/v1/admin/integrations/api-keys",
            json={"key_name": name, "scopes": scopes},
            headers=admin_headers,
        )
        assert response.status_code == 201
        payload = response.json()
        return payload["item"]["id"], payload["raw_key"]

    def _update_key_scopes(self, client, admin_headers, key_id: str, scopes: list[str]):
        response = client.put(
            f"/api/v1/admin/integrations/api-keys/{key_id}",
            json={"scopes": scopes},
            headers=admin_headers,
        )
        assert response.status_code == 200
        return response.json()

    def _set_key_enabled(self, client, admin_headers, key_id: str, enabled: bool):
        response = client.put(
            f"/api/v1/admin/integrations/api-keys/{key_id}",
            json={"enabled": enabled},
            headers=admin_headers,
        )
        assert response.status_code == 200
        return response.json()

    def test_agent_usage_requires_api_key(self, client):
        response = client.get("/api/agent/usage")
        assert response.status_code in (401, 403)

    def test_mcp_discovery_endpoints_share_disabled_access_guard(self, client, admin_headers):
        _key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "mcp-disabled",
            [AGENT_CONNECT, CONTENT_READ],
        )

        usage = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        meta = client.get("/api/mcp-meta", headers={"Authorization": f"Bearer {raw_key}"})
        healthz = client.get("/api/mcp-healthz", headers={"Authorization": f"Bearer {raw_key}"})

        assert usage.status_code == 403
        assert meta.status_code == 403
        assert healthz.status_code == 403
        assert usage.json()["detail"] == "MCP access is disabled"
        assert meta.json()["detail"] == "MCP access is disabled"
        assert healthz.json()["detail"] == "MCP access is disabled"

    def test_agent_usage_rejects_legacy_prefix_format(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "legacy-format",
            [AGENT_CONNECT, CONTENT_READ],
        )

        factory = get_session_factory()
        with factory() as session:
            key = session.get(ApiKey, key_id)
            assert key is not None
            key.key_prefix = raw_key[:8]
            session.commit()

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code in (401, 403)

    def test_agent_usage_returns_scope_filtered_capabilities(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        _key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "usage-docs",
            [AGENT_CONNECT, CONTENT_READ],
        )

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == "2026-03-usage-v2"
        endpoint_map = {item["id"]: item for item in data["endpoints"]}
        assert endpoint_map["usage_document"]["url"].endswith("/api/agent/usage")
        assert endpoint_map["mcp_streamable_http"]["url"].endswith("/api/mcp")
        assert data["scope_guide"]["available_on_current_key"] == [AGENT_CONNECT, CONTENT_READ]
        assert data["quickstart"]["steps"][0]["order"] == 1
        assert any(item["id"] == "list-content" for item in data["playbooks"])
        assert any(item["code"] == "403" for item in data["troubleshooting"])
        assert data["mcp"]["endpoint"].endswith("/api/mcp")
        assert data["mcp"]["available_scopes"] == [AGENT_CONNECT, CONTENT_READ]
        tool_names = {item["name"] for item in data["mcp"]["tools"]}
        resource_names = {item["name"] for item in data["mcp"]["resources"]}
        assert {
            "list_posts",
            "search_content",
            "list_diary_entries",
            "list_thoughts",
            "list_excerpts",
            "list_admin_content",
            "get_admin_content",
            "export_content",
            "list_admin_tags",
            "list_admin_content_categories",
        }.issubset(tool_names)
        assert "create_admin_content" not in tool_names
        assert "moderate_comment" not in tool_names
        assert {
            "aerisun://posts",
            "aerisun://diary",
            "aerisun://thoughts",
            "aerisun://excerpts",
            "aerisun://feeds/posts",
        }.issubset(resource_names)
        assert data["skill_maps"][0]["id"] == "comment-moderation"
        assert data["skill_maps"][0]["docs_url"].endswith("/api/agent/usage")
        assert data["skill_maps"][0]["where"]["endpoint"].endswith("/api/mcp")

    def test_agent_usage_rejects_disabled_api_key(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "disabled-usage-docs",
            [AGENT_CONNECT, CONTENT_READ],
        )
        response = self._set_key_enabled(client, admin_headers, key_id, False)
        assert response["enabled"] is False

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code in (401, 403)

    def test_agent_usage_includes_config_tool_when_scope_present(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        _key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "usage-docs-config",
            [AGENT_CONNECT, CONTENT_READ, CONFIG_READ],
        )

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        data = response.json()
        tool_names = [item["name"] for item in data["mcp"]["tools"]]
        resource_names = [item["name"] for item in data["mcp"]["resources"]]
        assert "get_site_config" in tool_names
        assert "aerisun://site-config" in resource_names

    def test_agent_usage_exposes_extended_read_surfaces_for_full_readonly_scope_set(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        _key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "usage-docs-readonly-full",
            READONLY_PRESET_SCOPES,
        )

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        tool_names = {item["name"] for item in response.json()["mcp"]["tools"]}
        assert {
            "get_subscription_config",
            "list_subscription_subscribers",
            "list_subscription_delivery_history",
            "get_visitor_auth_config",
            "list_visitor_users",
            "get_admin_login_options",
            "get_admin_me",
            "list_admin_sessions",
            "get_agent_model_config",
            "validate_agent_workflow",
            "get_agent_run_detail",
            "get_outbound_proxy_config",
            "get_system_info",
            "get_dashboard_stats",
            "list_audit_logs",
            "list_config_revisions",
            "get_config_revision_detail",
            "list_visitor_records",
            "list_admin_api_keys",
            "get_backup_sync_config",
            "list_backup_snapshots",
            "export_content",
        }.issubset(tool_names)

    def test_workflow_planning_context_uses_full_backend_capability_catalog(self, seeded_session):
        settings = get_settings()
        context = build_workflow_planning_usage_context(seeded_session, settings.site_url)

        capability_names = {item["name"] for item in context["capabilities"]}
        endpoint_ids = {item["id"] for item in context["endpoints"]}
        playbook_ids = {item["id"] for item in context["playbooks"]}

        assert "list_admin_content" in capability_names
        assert "create_admin_content" in capability_names
        assert "export_content" in capability_names
        assert "import_content" in capability_names
        assert "moderate_comment" in capability_names
        assert "get_site_config" in capability_names
        assert "validate_agent_workflow" in capability_names
        assert "test_agent_model_config" in capability_names
        assert "test_backup_sync_config" in capability_names
        assert "aerisun://site-config" in capability_names
        assert "usage_document" in endpoint_ids
        assert "mcp_streamable_http" in endpoint_ids
        assert "list-content" in playbook_ids

    def test_api_key_scope_presets_drive_agent_usage(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_id, _raw_key = self._create_key(
            client,
            admin_headers,
            "mcp-admin-config",
            READONLY_PRESET_SCOPES,
        )

        response = self._update_key_scopes(
            client,
            admin_headers,
            key_id,
            READONLY_PRESET_SCOPES,
        )
        assert response["scopes"] == sorted(READONLY_PRESET_SCOPES)

        response = client.get(f"/api/v1/admin/integrations/mcp-config?api_key_id={key_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["selected_preset"] == "readonly"
        assert data["api_key_id"] == key_id
        assert data["available_capability_count"] == len(data["capabilities"])
        assert data["available_capability_count"] > data["enabled_capability_count"]
        all_ids = {item["id"] for item in data["capabilities"]}
        enabled_ids = {item["id"] for item in data["capabilities"] if item["enabled"]}
        assert "tool:list_posts" in enabled_ids
        assert "tool:list_admin_content" in enabled_ids
        assert "tool:create_admin_content" in all_ids
        assert "tool:create_admin_content" not in enabled_ids
        assert "tool:moderate_comment" in all_ids
        assert "tool:moderate_comment" not in enabled_ids
        assert "tool:update_admin_site_profile" in all_ids
        assert "tool:update_admin_site_profile" not in enabled_ids

        response = self._update_key_scopes(
            client,
            admin_headers,
            key_id,
            BASIC_MANAGEMENT_PRESET_SCOPES,
        )
        assert CONTENT_WRITE in response["scopes"]

        response = client.get(f"/api/v1/admin/integrations/mcp-config?api_key_id={key_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        enabled_ids = {item["id"] for item in data["capabilities"] if item["enabled"]}
        assert data["selected_preset"] == "basic_management"
        assert data["is_customized"] is False
        assert "tool:create_admin_content" in enabled_ids
        assert "tool:moderate_comment" in enabled_ids
        assert "tool:update_admin_site_profile" not in enabled_ids
        assert "tool:upload_admin_asset" not in enabled_ids

        response = self._update_key_scopes(
            client,
            admin_headers,
            key_id,
            FULL_MANAGEMENT_PRESET_SCOPES,
        )
        assert ASSETS_WRITE in response["scopes"]

        response = client.get(f"/api/v1/admin/integrations/mcp-config?api_key_id={key_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        enabled_ids = {item["id"] for item in data["capabilities"] if item["enabled"]}
        assert data["selected_preset"] == "full_management"
        assert "tool:create_admin_content" in enabled_ids
        assert "tool:moderate_comment" in enabled_ids
        assert "tool:update_admin_site_profile" in enabled_ids
        assert "tool:upload_admin_asset" in enabled_ids

        response = self._update_key_scopes(
            client,
            admin_headers,
            key_id,
            [AGENT_CONNECT, CONTENT_READ, CONFIG_READ],
        )
        assert response["scopes"] == [AGENT_CONNECT, CONFIG_READ, CONTENT_READ]

        response = client.get(f"/api/v1/admin/integrations/mcp-config?api_key_id={key_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["selected_preset"] == "custom"
        assert data["is_customized"] is True
        enabled_ids = {item["id"] for item in data["capabilities"] if item["enabled"]}
        assert "tool:list_posts" in enabled_ids
        assert "resource:aerisun://posts" in enabled_ids
        assert "tool:update_admin_site_profile" not in enabled_ids

    def test_mcp_config_without_api_key_returns_full_catalog(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)

        response = client.get("/api/v1/admin/integrations/mcp-config", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["api_key_id"] is None
        assert data["available_capability_count"] == len(data["capabilities"])
        assert data["available_capability_count"] > 50
        assert all(not item["enabled"] for item in data["capabilities"])
        assert any(item["id"] == "tool:list_posts" for item in data["capabilities"])

    def test_management_tools_follow_key_scopes(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "usage-docs-manager",
            [
                AGENT_CONNECT,
                CONTENT_READ,
                CONTENT_WRITE,
                MODERATION_READ,
                MODERATION_WRITE,
            ],
        )
        self._update_key_scopes(
            client,
            admin_headers,
            key_id,
            [
                AGENT_CONNECT,
                CONTENT_READ,
                CONTENT_WRITE,
                MODERATION_READ,
                MODERATION_WRITE,
                CONFIG_READ,
                ASSETS_READ,
            ],
        )

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        tool_names = {item["name"] for item in response.json()["mcp"]["tools"]}
        assert "create_admin_content" in tool_names
        assert "update_admin_content" in tool_names
        assert "moderate_comment" in tool_names
        assert "moderate_guestbook_entry" in tool_names
        assert "update_admin_site_profile" not in tool_names
        assert "upload_admin_asset" not in tool_names

    def test_agent_usage_and_mcp_meta_follow_configured_capabilities(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "usage-docs-minimal",
            [AGENT_CONNECT, CONTENT_READ],
        )
        self._update_key_scopes(client, admin_headers, key_id, [AGENT_CONNECT, CONTENT_READ])

        usage = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert usage.status_code == 200
        usage_payload = usage.json()
        tool_names = {item["name"] for item in usage_payload["mcp"]["tools"]}
        resource_names = {item["name"] for item in usage_payload["mcp"]["resources"]}
        assert "list_posts" in tool_names
        assert "export_content" in tool_names
        assert "search_content" in tool_names
        assert "aerisun://posts" in resource_names

        mcp_meta = client.get("/api/mcp-meta", headers={"Authorization": f"Bearer {raw_key}"})
        assert mcp_meta.status_code == 200
        meta_payload = mcp_meta.json()
        assert "list_posts" in meta_payload["tools"]
        assert "aerisun://posts" in meta_payload["resources"]

    def test_mcp_meta_exposes_new_management_capabilities(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        _key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "usage-docs-new-management",
            [
                AGENT_CONNECT,
                CONTENT_READ,
                CONTENT_WRITE,
                AUTH_READ,
                AUTOMATION_READ,
                AUTOMATION_WRITE,
                SYSTEM_READ,
                SYSTEM_WRITE,
            ],
        )

        response = client.get("/api/mcp-meta", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        tool_names = set(response.json()["tools"])
        assert {
            "export_content",
            "import_content",
            "get_admin_me",
            "list_admin_sessions",
            "validate_agent_workflow",
            "test_agent_model_config",
            "trigger_workflow_run",
            "test_workflow_run",
            "test_backup_sync_config",
        }.issubset(tool_names)

    def test_api_key_scopes_are_stored_per_api_key(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_a_id, key_a_raw = self._create_key(
            client,
            admin_headers,
            "key-a",
            [AGENT_CONNECT, CONTENT_READ],
        )
        key_b_id, key_b_raw = self._create_key(
            client,
            admin_headers,
            "key-b",
            [AGENT_CONNECT, CONTENT_READ],
        )

        self._update_key_scopes(client, admin_headers, key_a_id, [AGENT_CONNECT, CONTENT_READ])
        self._update_key_scopes(client, admin_headers, key_b_id, [AGENT_CONNECT, CONTENT_READ, CONFIG_READ])

        usage_a = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {key_a_raw}"})
        usage_b = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {key_b_raw}"})
        assert usage_a.status_code == 200
        assert usage_b.status_code == 200
        tool_names_a = {item["name"] for item in usage_a.json()["mcp"]["tools"]}
        assert "list_posts" in tool_names_a
        assert "create_admin_content" not in tool_names_a
        assert "get_site_config" in [item["name"] for item in usage_b.json()["mcp"]["tools"]]
        assert "aerisun://site-config" in [item["name"] for item in usage_b.json()["mcp"]["resources"]]
