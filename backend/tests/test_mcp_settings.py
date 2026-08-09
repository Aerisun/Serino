from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

import pytest

from aerisun.api.admin.scopes import AGENT_CONNECT, CONTENT_READ
from aerisun.core.time import normalize_shanghai_datetime, shanghai_now
from aerisun.domain.agent.mcp_introspection import list_registered_mcp_capabilities
from aerisun.domain.agent.mcp_settings import resolve_mcp_config
from aerisun.domain.exceptions import PermissionDenied
from aerisun.domain.iam.models import ApiKey
from aerisun.domain.iam.service import create_api_key, validate_api_key

MCP_CONFIG_URL = "/api/v1/admin/integrations/mcp-config"


def _create_key(session, name: str, scopes: list[str]) -> tuple[ApiKey, str]:
    created = create_api_key(session, name, scopes)
    key = session.get(ApiKey, created.item.id)
    assert key is not None
    return key, created.raw_key


def _enable_mcp(client, admin_headers) -> None:
    response = client.put(MCP_CONFIG_URL, json={"public_access": True}, headers=admin_headers)
    assert response.status_code == 200


def _create_key_over_http(client, admin_headers, name: str, scopes: list[str]) -> tuple[str, str]:
    response = client.post(
        "/api/v1/admin/integrations/api-keys",
        json={"key_name": name, "scopes": scopes},
        headers=admin_headers,
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["item"]["id"], payload["raw_key"]


def test_explicit_capability_ids_resolve_to_the_scope_intersection(seeded_session) -> None:
    key, _raw_key = _create_key(
        seeded_session,
        "explicit-capabilities",
        [AGENT_CONNECT, CONTENT_READ],
    )
    key.mcp_config = {
        "enabled_capability_ids": [
            "tool:list_posts",
            "resource:aerisun://posts",
            "tool:get_site_config",
        ]
    }
    seeded_session.commit()

    resolved = resolve_mcp_config(
        seeded_session,
        list_registered_mcp_capabilities(),
        api_key=key,
    )

    assert resolved.enabled_capability_ids == [
        "resource:aerisun://posts",
        "tool:list_posts",
    ]
    assert resolved.selected_preset == "custom"
    assert resolved.is_customized is True


def test_selected_preset_cannot_expand_key_scopes(seeded_session) -> None:
    key, _raw_key = _create_key(
        seeded_session,
        "full-preset-readonly-key",
        [AGENT_CONNECT, CONTENT_READ],
    )
    key.mcp_config = {"selected_preset": "full_management"}
    seeded_session.commit()

    resolved = resolve_mcp_config(
        seeded_session,
        list_registered_mcp_capabilities(),
        api_key=key,
    )

    assert resolved.selected_preset == "full_management"
    assert resolved.is_customized is False
    assert "tool:list_posts" in resolved.enabled_capability_ids
    assert "tool:create_admin_content" not in resolved.enabled_capability_ids
    assert "tool:get_site_config" not in resolved.enabled_capability_ids


@pytest.mark.parametrize(
    "stored_config",
    [
        {"selected_preset": "unknown"},
        {"enabled_capability_ids": ["tool:not-registered"]},
        {"selected_preset": "readonly", "extra": True},
        {"enabled_capability_ids": "tool:list_posts"},
    ],
)
def test_malformed_persisted_config_fails_closed(seeded_session, stored_config) -> None:
    key, _raw_key = _create_key(
        seeded_session,
        "malformed-config",
        [AGENT_CONNECT, CONTENT_READ],
    )
    key.mcp_config = stored_config
    seeded_session.commit()

    resolved = resolve_mcp_config(
        seeded_session,
        list_registered_mcp_capabilities(),
        api_key=key,
    )

    assert resolved.enabled_capability_ids == []
    assert resolved.selected_preset == "custom"
    assert resolved.is_customized is True


def test_admin_update_saves_minimal_explicit_capability_config(client, admin_headers) -> None:
    _enable_mcp(client, admin_headers)
    key_id, raw_key = _create_key_over_http(
        client,
        admin_headers,
        "custom-capability-key",
        [AGENT_CONNECT, CONTENT_READ],
    )

    response = client.put(
        MCP_CONFIG_URL,
        params={"api_key_id": key_id},
        json={"enabled_capability_ids": ["resource:aerisun://posts", "tool:list_posts"]},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["selected_preset"] == "custom"
    assert payload["is_customized"] is True
    assert {item["id"] for item in payload["capabilities"] if item["enabled"]} == {
        "resource:aerisun://posts",
        "tool:list_posts",
    }

    usage = client.get("/api/agent/usage", headers={"Authorization": f"Bearer {raw_key}"})
    meta = client.get("/api/mcp-meta", headers={"Authorization": f"Bearer {raw_key}"})
    assert usage.status_code == 200
    assert meta.status_code == 200
    assert {item["id"] for item in usage.json()["mcp"]["tools"]} == {"tool:list_posts"}
    assert {item["id"] for item in usage.json()["mcp"]["resources"]} == {"resource:aerisun://posts"}
    assert meta.json()["tools"] == ["list_posts"]
    assert meta.json()["resources"] == ["aerisun://posts"]

    from aerisun.core.db import get_session_factory

    with get_session_factory()() as session:
        key = session.get(ApiKey, key_id)
        assert key is not None
        assert key.mcp_config == {"enabled_capability_ids": ["resource:aerisun://posts", "tool:list_posts"]}


def test_admin_update_saves_minimal_preset_config(client, admin_headers) -> None:
    key_id, _raw_key = _create_key_over_http(
        client,
        admin_headers,
        "preset-config-key",
        [AGENT_CONNECT, CONTENT_READ],
    )

    response = client.put(
        MCP_CONFIG_URL,
        params={"api_key_id": key_id},
        json={"selected_preset": "readonly"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["selected_preset"] == "readonly"
    assert response.json()["is_customized"] is False

    from aerisun.core.db import get_session_factory

    with get_session_factory()() as session:
        key = session.get(ApiKey, key_id)
        assert key is not None
        assert key.mcp_config == {"selected_preset": "readonly"}


def test_admin_update_accepts_an_explicit_empty_capability_list(client, admin_headers) -> None:
    key_id, _raw_key = _create_key_over_http(
        client,
        admin_headers,
        "disabled-catalog-key",
        [AGENT_CONNECT, CONTENT_READ],
    )

    response = client.put(
        MCP_CONFIG_URL,
        params={"api_key_id": key_id},
        json={"enabled_capability_ids": []},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["enabled_capability_count"] == 0
    assert response.json()["selected_preset"] == "custom"


@pytest.mark.parametrize(
    ("query", "body", "expected_detail"),
    [
        ({}, {"selected_preset": "readonly"}, "api_key_id is required"),
        (
            {"api_key_id": "{key_id}"},
            {"selected_preset": "readonly", "enabled_capability_ids": []},
            "mutually exclusive",
        ),
        ({"api_key_id": "{key_id}"}, {"selected_preset": "unknown"}, "Unknown MCP preset"),
        (
            {"api_key_id": "{key_id}"},
            {"enabled_capability_ids": ["tool:not-registered"]},
            "Unknown capability IDs",
        ),
        (
            {"api_key_id": "{key_id}"},
            {"enabled_capability_ids": ["tool:get_site_config"]},
            "not available to this API key",
        ),
    ],
)
def test_admin_update_rejects_invalid_per_key_config(
    client,
    admin_headers,
    query,
    body,
    expected_detail,
) -> None:
    key_id, _raw_key = _create_key_over_http(
        client,
        admin_headers,
        "invalid-config-key",
        [AGENT_CONNECT, CONTENT_READ],
    )
    resolved_query = {name: value.format(key_id=key_id) for name, value in query.items()}

    response = client.put(
        MCP_CONFIG_URL,
        params=resolved_query,
        json=body,
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]


def test_admin_update_rejects_removed_or_unknown_configuration_fields(client, admin_headers) -> None:
    response = client.put(
        MCP_CONFIG_URL,
        json={"confirm_before_write": True},
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert any(item["type"] == "extra_forbidden" for item in response.json()["detail"])


def test_recent_api_key_use_does_not_commit(seeded_session, monkeypatch) -> None:
    key, raw_key = _create_key(
        seeded_session,
        "recently-used",
        [AGENT_CONNECT, CONTENT_READ],
    )
    recent = shanghai_now() - timedelta(minutes=4)
    key.last_used_at = recent
    seeded_session.commit()
    seeded_session.expire(key, ["last_used_at"])
    commit = Mock(wraps=seeded_session.commit)
    monkeypatch.setattr(seeded_session, "commit", commit)

    validated = validate_api_key(seeded_session, raw_key, (AGENT_CONNECT,))

    assert validated.id == key.id
    assert validated.last_used_at is not None
    assert normalize_shanghai_datetime(validated.last_used_at) == recent
    commit.assert_not_called()


def test_api_key_use_after_write_window_updates_timestamp(seeded_session, monkeypatch) -> None:
    key, raw_key = _create_key(
        seeded_session,
        "stale-last-used",
        [AGENT_CONNECT, CONTENT_READ],
    )
    stale = shanghai_now() - timedelta(minutes=6)
    key.last_used_at = stale
    seeded_session.commit()
    seeded_session.expire(key, ["last_used_at"])
    commit = Mock(wraps=seeded_session.commit)
    monkeypatch.setattr(seeded_session, "commit", commit)

    validated = validate_api_key(seeded_session, raw_key, (AGENT_CONNECT,))

    assert validated.last_used_at is not None
    assert normalize_shanghai_datetime(validated.last_used_at) > stale
    commit.assert_called_once_with()


def test_disabled_api_key_is_rejected_without_waiting_for_usage_window(seeded_session) -> None:
    key, raw_key = _create_key(
        seeded_session,
        "revoked-key",
        [AGENT_CONNECT, CONTENT_READ],
    )
    key.last_used_at = shanghai_now()
    key.enabled = False
    seeded_session.commit()

    with pytest.raises(PermissionDenied, match="API key is disabled"):
        validate_api_key(seeded_session, raw_key, (AGENT_CONNECT,))
