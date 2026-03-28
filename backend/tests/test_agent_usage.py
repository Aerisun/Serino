from __future__ import annotations

from aerisun.api.admin.scopes import MCP_CONFIG_READ, MCP_CONNECT, MCP_CONTENT_READ


class TestAgentUsage:
    def test_agent_usage_requires_api_key(self, client):
        response = client.get("/api/agent/usage")
        assert response.status_code in (401, 403)

    def test_agent_usage_returns_scope_filtered_capabilities(self, client, admin_headers):
        profile = client.get("/api/v1/admin/site-config/profile", headers=admin_headers)
        assert profile.status_code == 200
        payload = profile.json()
        update = {
            "name": payload["name"],
            "title": payload["title"],
            "bio": payload["bio"],
            "role": payload["role"],
            "footer_text": payload["footer_text"],
            "feature_flags": {**(payload.get("feature_flags") or {}), "mcp_public_access": True},
        }
        enabled = client.put("/api/v1/admin/site-config/profile", json=update, headers=admin_headers)
        assert enabled.status_code == 200

        create_key = client.post(
            "/api/v1/admin/system/api-keys",
            json={"key_name": "usage-docs", "scopes": [MCP_CONNECT, MCP_CONTENT_READ]},
            headers=admin_headers,
        )
        assert create_key.status_code == 201
        raw_key = create_key.json()["raw_key"]

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        data = response.json()
        assert data["docs_url"].endswith("/api/agent/usage")
        assert data["mcp"]["endpoint"].endswith("/api/mcp")
        assert data["mcp"]["available_scopes"] == [MCP_CONNECT, MCP_CONTENT_READ]
        assert [item["name"] for item in data["mcp"]["tools"]] == ["list_posts", "get_post", "search_content"]
        assert [item["name"] for item in data["mcp"]["resources"]] == [
            "aerisun://posts",
            "aerisun://posts/{slug}",
            "aerisun://feeds/posts",
        ]
        assert data["skill_maps"][0]["id"] == "comment-moderation"
        assert data["skill_maps"][0]["docs_url"].endswith("/api/agent/usage")

    def test_agent_usage_includes_config_tool_when_scope_present(self, client, admin_headers):
        profile = client.get("/api/v1/admin/site-config/profile", headers=admin_headers)
        payload = profile.json()
        enabled = client.put(
            "/api/v1/admin/site-config/profile",
            json={
                "name": payload["name"],
                "title": payload["title"],
                "bio": payload["bio"],
                "role": payload["role"],
                "footer_text": payload["footer_text"],
                "feature_flags": {**(payload.get("feature_flags") or {}), "mcp_public_access": True},
            },
            headers=admin_headers,
        )
        assert enabled.status_code == 200

        create_key = client.post(
            "/api/v1/admin/system/api-keys",
            json={"key_name": "usage-docs-config", "scopes": [MCP_CONNECT, MCP_CONTENT_READ, MCP_CONFIG_READ]},
            headers=admin_headers,
        )
        raw_key = create_key.json()["raw_key"]

        response = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
        assert response.status_code == 200
        data = response.json()
        tool_names = [item["name"] for item in data["mcp"]["tools"]]
        resource_names = [item["name"] for item in data["mcp"]["resources"]]
        assert "get_site_config" in tool_names
        assert "aerisun://site-config" in resource_names
