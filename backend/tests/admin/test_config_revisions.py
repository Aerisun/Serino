from __future__ import annotations

BASE = "/api/v1/admin/system"
SITE_CONFIG_BASE = "/api/v1/admin/site-config"
VISITORS_BASE = "/api/v1/admin/visitors"
SUBSCRIPTIONS_BASE = "/api/v1/admin/subscriptions"
AUTOMATION_BASE = "/api/v1/admin/automation"
INTEGRATIONS_BASE = "/api/v1/admin/integrations"
PROXY_BASE = "/api/v1/admin/proxy-config"


def _list_revisions(client, admin_headers, *, resource_key: str | None = None) -> list[dict[str, object]]:
    params = {"resource_key": resource_key} if resource_key else None
    response = client.get(f"{BASE}/config-revisions", headers=admin_headers, params=params)
    assert response.status_code == 200
    return response.json()["items"]


def _get_revision_detail(client, admin_headers, revision_id: str) -> dict[str, object]:
    response = client.get(f"{BASE}/config-revisions/{revision_id}", headers=admin_headers)
    assert response.status_code == 200
    return response.json()


def test_profile_config_revision_round_trip_and_audit_link(client, admin_headers) -> None:
    profile = client.get(f"{SITE_CONFIG_BASE}/profile", headers=admin_headers).json()
    original_title = profile["title"]

    response = client.put(
        f"{SITE_CONFIG_BASE}/profile",
        headers=admin_headers,
        json={"title": "Config Revision Profile Title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Config Revision Profile Title"

    revisions = _list_revisions(client, admin_headers, resource_key="site.profile")
    assert revisions
    latest = revisions[0]
    assert latest["resource_key"] == "site.profile"
    assert latest["operation"] == "update"

    detail = _get_revision_detail(client, admin_headers, str(latest["id"]))
    assert any(line["path"] == "title" for line in detail["diff_lines"])
    assert detail["before_preview"]["title"] == original_title
    assert detail["after_preview"]["title"] == "Config Revision Profile Title"

    restore_response = client.post(
        f"{BASE}/config-revisions/{latest['id']}/restore",
        headers=admin_headers,
        json={"target": "before", "reason": "rollback test"},
    )
    assert restore_response.status_code == 200
    restored = client.get(f"{SITE_CONFIG_BASE}/profile", headers=admin_headers)
    assert restored.status_code == 200
    assert restored.json()["title"] == original_title

    revisions_after = _list_revisions(client, admin_headers, resource_key="site.profile")
    assert revisions_after[0]["operation"] == "restore"
    assert revisions_after[0]["restored_from_revision_id"] == latest["id"]

    audit_logs = client.get(f"{BASE}/audit-logs", headers=admin_headers)
    assert audit_logs.status_code == 200
    assert any(
        item["payload"].get("config_revision_id") == latest["id"]
        and item["payload"].get("resource_key") == "site.profile"
        for item in audit_logs.json()["items"]
    )


def test_community_config_revision_detail_lists_changed_fields(client, admin_headers) -> None:
    current = client.get(f"{SITE_CONFIG_BASE}/community-config", headers=admin_headers)
    assert current.status_code == 200

    response = client.put(
        f"{SITE_CONFIG_BASE}/community-config",
        headers=admin_headers,
        json={
            "moderation_mode": "no_review",
            "default_sorting": "oldest",
            "page_size": 30,
            "avatar_helper_copy": "登录后再评论",
        },
    )
    assert response.status_code == 200

    latest = _list_revisions(client, admin_headers, resource_key="site.community")[0]
    detail = _get_revision_detail(client, admin_headers, str(latest["id"]))
    paths = {line["path"] for line in detail["diff_lines"]}
    assert "moderation_mode" in paths
    assert "default_sorting" in paths
    assert "page_size" in paths
    assert "avatar_helper_copy" in paths


def test_navigation_delete_restore_recreates_item(client, admin_headers) -> None:
    create_response = client.post(
        f"{SITE_CONFIG_BASE}/nav-items/",
        headers=admin_headers,
        json={
            "label": "Config Revision Link",
            "href": "/config-revision-link",
            "trigger": "none",
            "order_index": 99,
            "is_enabled": True,
        },
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]

    delete_response = client.delete(f"{SITE_CONFIG_BASE}/nav-items/{item_id}", headers=admin_headers)
    assert delete_response.status_code == 204

    latest = _list_revisions(client, admin_headers, resource_key="site.navigation")[0]
    assert latest["operation"] == "delete"

    restore_response = client.post(
        f"{BASE}/config-revisions/{latest['id']}/restore",
        headers=admin_headers,
        json={"target": "before"},
    )
    assert restore_response.status_code == 200

    nav_items = client.get(f"{SITE_CONFIG_BASE}/nav-items/", headers=admin_headers)
    assert nav_items.status_code == 200
    assert any(item["id"] == item_id for item in nav_items.json()["items"])


def test_page_copy_updates_create_site_pages_revision(client, admin_headers) -> None:
    pages = client.get(f"{SITE_CONFIG_BASE}/page-copy/", headers=admin_headers)
    assert pages.status_code == 200
    first_page = pages.json()["items"][0]

    update_page = client.put(
        f"{SITE_CONFIG_BASE}/page-copy/{first_page['id']}",
        headers=admin_headers,
        json={"title": "Config Revision Page Title"},
    )
    assert update_page.status_code == 200

    first_revision = _list_revisions(client, admin_headers, resource_key="site.pages")[0]
    assert first_revision["resource_key"] == "site.pages"


def test_sensitive_config_previews_are_masked_and_restore_works(client, admin_headers) -> None:
    model_config = client.put(
        f"{AUTOMATION_BASE}/model-config",
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "api_key": "secret-key-value",
        },
    )
    assert model_config.status_code == 200

    latest_model_revision = _list_revisions(client, admin_headers, resource_key="automation.model_config")[0]
    model_detail = _get_revision_detail(client, admin_headers, str(latest_model_revision["id"]))
    assert model_detail["after_preview"]["api_key"].startswith("******")
    assert model_detail["after_preview"]["api_key"].endswith("alue")

    restore_response = client.post(
        f"{BASE}/config-revisions/{latest_model_revision['id']}/restore",
        headers=admin_headers,
        json={"target": "before"},
    )
    assert restore_response.status_code == 200
    restored_config = client.get(f"{AUTOMATION_BASE}/model-config", headers=admin_headers)
    assert restored_config.status_code == 200
    assert restored_config.json()["api_key"] == ""

    visitors = client.put(
        f"{VISITORS_BASE}/config",
        headers=admin_headers,
        json={
            "google_client_id": "client-id",
            "google_client_secret": "visitor-google-secret",
        },
    )
    assert visitors.status_code == 200
    visitors_revision = _list_revisions(client, admin_headers, resource_key="visitors.auth")[0]
    visitors_detail = _get_revision_detail(client, admin_headers, str(visitors_revision["id"]))
    assert visitors_detail["after_preview"]["google_client_secret"].startswith("******")

    subscription = client.put(
        f"{SUBSCRIPTIONS_BASE}/config",
        headers=admin_headers,
        json={
            "smtp_host": "smtp.example.com",
            "smtp_password": "super-secret-password",
            "smtp_from_email": "no-reply@example.com",
        },
    )
    assert subscription.status_code == 200
    subscription_revision = _list_revisions(client, admin_headers, resource_key="subscriptions.config")[0]
    subscription_detail = _get_revision_detail(client, admin_headers, str(subscription_revision["id"]))
    assert subscription_detail["after_preview"]["smtp_password"].startswith("******")


def test_outbound_proxy_config_revision_roundtrip(client, admin_headers) -> None:
    current = client.get(PROXY_BASE, headers=admin_headers)
    assert current.status_code == 200
    original = current.json()

    response = client.put(
        PROXY_BASE,
        headers=admin_headers,
        json={"proxy_port": 7890, "webhook_enabled": True},
    )
    assert response.status_code == 200

    latest = _list_revisions(client, admin_headers, resource_key="network.outbound_proxy")[0]
    assert latest["resource_key"] == "network.outbound_proxy"

    detail = _get_revision_detail(client, admin_headers, str(latest["id"]))
    paths = {line["path"] for line in detail["diff_lines"]}
    assert "proxy_port" in paths
    assert "webhook_enabled" in paths

    restore_response = client.post(
        f"{BASE}/config-revisions/{latest['id']}/restore",
        headers=admin_headers,
        json={"target": "before"},
    )
    assert restore_response.status_code == 200

    restored = client.get(PROXY_BASE, headers=admin_headers)
    assert restored.status_code == 200
    assert restored.json() == original


def test_config_revision_failure_paths_and_mcp_tracking(client, admin_headers) -> None:
    before_workflow_count = len(_list_revisions(client, admin_headers, resource_key="automation.workflows"))

    missing_workflow = client.put(
        f"{AUTOMATION_BASE}/workflows/does-not-exist",
        headers=admin_headers,
        json={"name": "Nope"},
    )
    assert missing_workflow.status_code == 404

    after_workflow_count = len(_list_revisions(client, admin_headers, resource_key="automation.workflows"))
    assert after_workflow_count == before_workflow_count

    restore_missing = client.post(
        f"{BASE}/config-revisions/nonexistent-revision/restore",
        headers=admin_headers,
        json={"target": "before"},
    )
    assert restore_missing.status_code == 404

    mcp_response = client.put(
        f"{INTEGRATIONS_BASE}/mcp-config",
        headers=admin_headers,
        json={"public_access": True},
    )
    assert mcp_response.status_code == 200
    latest = _list_revisions(client, admin_headers, resource_key="integrations.mcp_public_access")[0]
    assert latest["resource_key"] == "integrations.mcp_public_access"
