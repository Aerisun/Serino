from __future__ import annotations

from aerisun.api.admin.scopes import (
    MCP_ASSETS_READ,
    MCP_ASSETS_WRITE,
    MCP_CONFIG_READ,
    MCP_CONFIG_WRITE,
    MCP_CONNECT,
    MCP_CONTENT_READ,
    MCP_CONTENT_WRITE,
    MCP_MODERATION_READ,
    MCP_MODERATION_WRITE,
)
from aerisun.core.db import get_session_factory
from aerisun.domain.iam.models import ApiKey


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
            "/api/v1/admin/system/api-keys",
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

    def test_agent_usage_requires_api_key(self, client):
        response = client.get("/api/agent/usage")
        assert response.status_code in (401, 403)

    def test_agent_usage_rejects_legacy_prefix_format(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "legacy-format",
            [MCP_CONNECT, MCP_CONTENT_READ],
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
            [MCP_CONNECT, MCP_CONTENT_READ],
        )

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == "2026-03-usage-v2"
        endpoint_map = {item["id"]: item for item in data["endpoints"]}
        assert endpoint_map["usage_document"]["url"].endswith("/api/agent/usage")
        assert endpoint_map["mcp_streamable_http"]["url"].endswith("/api/mcp/mcp")
        assert data["scope_guide"]["available_on_current_key"] == [MCP_CONNECT, MCP_CONTENT_READ]
        assert data["quickstart"]["steps"][0]["order"] == 1
        assert any(item["id"] == "list-content" for item in data["playbooks"])
        assert any(item["code"] == "403" for item in data["troubleshooting"])
        assert data["mcp"]["endpoint"].endswith("/api/mcp/mcp")
        assert data["mcp"]["available_scopes"] == [MCP_CONNECT, MCP_CONTENT_READ]
        tool_names = {item["name"] for item in data["mcp"]["tools"]}
        resource_names = {item["name"] for item in data["mcp"]["resources"]}
        assert {
            "list_posts",
            "get_post",
            "search_content",
            "list_diary_entries",
            "get_diary_entry",
            "list_thoughts",
            "list_excerpts",
            "list_admin_content",
            "get_admin_content",
            "list_admin_tags",
            "list_admin_content_categories",
        }.issubset(tool_names)
        assert "create_admin_content" not in tool_names
        assert "moderate_comment" not in tool_names
        assert {
            "aerisun://posts",
            "aerisun://posts/{slug}",
            "aerisun://diary",
            "aerisun://diary/{slug}",
            "aerisun://thoughts",
            "aerisun://excerpts",
            "aerisun://feeds/posts",
        }.issubset(resource_names)
        assert data["skill_maps"][0]["id"] == "comment-moderation"
        assert data["skill_maps"][0]["docs_url"].endswith("/api/agent/usage")
        assert data["skill_maps"][0]["where"]["endpoint"].endswith("/api/mcp/mcp")

    def test_agent_usage_includes_config_tool_when_scope_present(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        _key_id, raw_key = self._create_key(
            client,
            admin_headers,
            "usage-docs-config",
            [MCP_CONNECT, MCP_CONTENT_READ, MCP_CONFIG_READ],
        )

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        data = response.json()
        tool_names = [item["name"] for item in data["mcp"]["tools"]]
        resource_names = [item["name"] for item in data["mcp"]["resources"]]
        assert "get_site_config" in tool_names
        assert "aerisun://site-config" in resource_names

    def test_api_key_scope_presets_drive_agent_usage(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_id, _raw_key = self._create_key(
            client,
            admin_headers,
            "mcp-admin-config",
            [
                MCP_CONNECT,
                MCP_CONTENT_READ,
                MCP_MODERATION_READ,
                MCP_CONFIG_READ,
                MCP_ASSETS_READ,
            ],
        )

        response = self._update_key_scopes(
            client,
            admin_headers,
            key_id,
            [MCP_CONNECT, MCP_CONTENT_READ, MCP_MODERATION_READ, MCP_CONFIG_READ, MCP_ASSETS_READ],
        )
        assert response["scopes"] == [
            MCP_ASSETS_READ,
            MCP_CONFIG_READ,
            MCP_CONNECT,
            MCP_CONTENT_READ,
            MCP_MODERATION_READ,
        ]

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
            [
                MCP_CONNECT,
                MCP_CONTENT_READ,
                MCP_CONTENT_WRITE,
                MCP_MODERATION_READ,
                MCP_MODERATION_WRITE,
                MCP_CONFIG_READ,
                MCP_ASSETS_READ,
            ],
        )
        assert MCP_CONTENT_WRITE in response["scopes"]

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
            [
                MCP_CONNECT,
                MCP_CONTENT_READ,
                MCP_CONTENT_WRITE,
                MCP_MODERATION_READ,
                MCP_MODERATION_WRITE,
                MCP_CONFIG_READ,
                MCP_CONFIG_WRITE,
                MCP_ASSETS_READ,
                MCP_ASSETS_WRITE,
            ],
        )
        assert MCP_ASSETS_WRITE in response["scopes"]

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
            [MCP_CONNECT, MCP_CONTENT_READ, MCP_CONFIG_READ],
        )
        assert response["scopes"] == [MCP_CONFIG_READ, MCP_CONNECT, MCP_CONTENT_READ]

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
                MCP_CONNECT,
                MCP_CONTENT_READ,
                MCP_CONTENT_WRITE,
                MCP_MODERATION_READ,
                MCP_MODERATION_WRITE,
            ],
        )
        self._update_key_scopes(
            client,
            admin_headers,
            key_id,
            [
                MCP_CONNECT,
                MCP_CONTENT_READ,
                MCP_CONTENT_WRITE,
                MCP_MODERATION_READ,
                MCP_MODERATION_WRITE,
                MCP_CONFIG_READ,
                MCP_ASSETS_READ,
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
            [MCP_CONNECT, MCP_CONTENT_READ],
        )
        self._update_key_scopes(client, admin_headers, key_id, [MCP_CONNECT, MCP_CONTENT_READ])

        usage = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert usage.status_code == 200
        usage_payload = usage.json()
        tool_names = {item["name"] for item in usage_payload["mcp"]["tools"]}
        resource_names = {item["name"] for item in usage_payload["mcp"]["resources"]}
        assert "list_posts" in tool_names
        assert "get_post" in tool_names
        assert "search_content" in tool_names
        assert "aerisun://posts" in resource_names

        mcp_meta = client.get("/api/mcp-meta", headers={"Authorization": f"Bearer {raw_key}"})
        assert mcp_meta.status_code == 200
        meta_payload = mcp_meta.json()
        assert "list_posts" in meta_payload["tools"]
        assert "aerisun://posts" in meta_payload["resources"]

    def test_api_key_scopes_are_stored_per_api_key(self, client, admin_headers):
        self._enable_mcp(client, admin_headers)
        key_a_id, key_a_raw = self._create_key(
            client,
            admin_headers,
            "key-a",
            [MCP_CONNECT, MCP_CONTENT_READ],
        )
        key_b_id, key_b_raw = self._create_key(
            client,
            admin_headers,
            "key-b",
            [MCP_CONNECT, MCP_CONTENT_READ],
        )

        self._update_key_scopes(client, admin_headers, key_a_id, [MCP_CONNECT, MCP_CONTENT_READ])
        self._update_key_scopes(client, admin_headers, key_b_id, [MCP_CONNECT, MCP_CONTENT_READ, MCP_CONFIG_READ])

        usage_a = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {key_a_raw}"})
        usage_b = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {key_b_raw}"})
        assert usage_a.status_code == 200
        assert usage_b.status_code == 200
        tool_names_a = {item["name"] for item in usage_a.json()["mcp"]["tools"]}
        assert "list_posts" in tool_names_a
        assert "create_admin_content" not in tool_names_a
        assert "get_site_config" in [item["name"] for item in usage_b.json()["mcp"]["tools"]]
        assert "aerisun://site-config" in [item["name"] for item in usage_b.json()["mcp"]["resources"]]
