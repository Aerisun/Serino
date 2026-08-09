from __future__ import annotations

from aerisun.domain.automation.codex_app_server import (
    CodexAccount,
    CodexDeviceLogin,
    CodexLoginStatus,
    CodexModel,
)
from aerisun.domain.exceptions import ValidationError

ADMIN_BASE = "/api/v1/admin/automation"


class _FakeCodexClient:
    def __init__(self) -> None:
        self.logged_out = False

    def read_account(self, *, refresh_token: bool = False):
        return CodexAccount(email="owner@example.com", plan_type="plus")

    def start_device_login(self):
        return CodexDeviceLogin(
            login_id="login-1",
            verification_url="https://auth.openai.com/device",
            user_code="ABCD-EFGH",
        )

    def get_login_status(self, login_id: str):
        assert login_id == "login-1"
        return CodexLoginStatus(
            status="completed",
            account=CodexAccount(email="owner@example.com", plan_type="plus"),
        )

    def logout(self) -> None:
        self.logged_out = True

    def list_models(self):
        return [CodexModel(model="gpt-5.2-codex", display_name="GPT-5.2 Codex", is_default=True)]


def test_admin_can_manage_one_chatgpt_oauth_account(client, admin_headers, monkeypatch) -> None:
    fake_client = _FakeCodexClient()
    health_resets: list[str | None] = []
    monkeypatch.setattr(
        "aerisun.domain.automation.model_management.get_codex_app_server_client",
        lambda: fake_client,
    )
    monkeypatch.setattr(
        "aerisun.domain.automation.model_management.reset_model_source_health",
        lambda source=None: health_resets.append(source),
    )
    proxy_response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={"proxy_port": 7890, "oauth_enabled": True},
    )
    assert proxy_response.status_code == 200

    account_response = client.get(f"{ADMIN_BASE}/model-config/chatgpt/account", headers=admin_headers)
    assert account_response.status_code == 200
    assert account_response.json() == {
        "connected": True,
        "email": "owner@example.com",
        "plan_type": "plus",
        "error": None,
    }

    login_response = client.post(f"{ADMIN_BASE}/model-config/chatgpt/login", headers=admin_headers)
    assert login_response.status_code == 200
    assert login_response.json()["user_code"] == "ABCD-EFGH"

    status_response = client.get(
        f"{ADMIN_BASE}/model-config/chatgpt/login/login-1",
        headers=admin_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["account"]["plan_type"] == "plus"

    models_response = client.get(f"{ADMIN_BASE}/model-config/chatgpt/models", headers=admin_headers)
    assert models_response.status_code == 200
    assert models_response.json() == [{"model": "gpt-5.2-codex", "display_name": "GPT-5.2 Codex", "is_default": True}]

    logout_response = client.delete(f"{ADMIN_BASE}/model-config/chatgpt/account", headers=admin_headers)
    assert logout_response.status_code == 204
    assert fake_client.logged_out is True
    assert health_resets == ["chatgpt_oauth", "chatgpt_oauth"]


def test_model_diagnostics_warn_when_only_the_fallback_source_fails(client, admin_headers, monkeypatch) -> None:
    proxy_response = client.put(
        "/api/v1/admin/proxy-config",
        headers=admin_headers,
        json={"proxy_port": 7890, "oauth_enabled": True},
    )
    assert proxy_response.status_code == 200
    update_response = client.put(
        f"{ADMIN_BASE}/model-config",
        headers=admin_headers,
        json={
            "primary_source": "chatgpt_oauth",
            "chatgpt_oauth": {"enabled": True, "model": "gpt-5.2-codex"},
            "openai_compatible": {
                "enabled": True,
                "base_url": "https://api.example.test/v1",
                "model": "fallback-model",
                "api_key": "secret-key",
            },
        },
    )
    assert update_response.status_code == 200

    monkeypatch.setattr(
        "aerisun.domain.automation.model_management.probe_chatgpt_config",
        lambda config: {"model": config["model"], "summary": "connection_ok"},
    )
    monkeypatch.setattr(
        "aerisun.domain.automation.model_management.probe_model_config",
        lambda config: (_ for _ in ()).throw(ValidationError("fallback offline")),
    )

    response = client.post(f"{ADMIN_BASE}/model-config/diagnose", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "warning"
    assert payload["active_source"] == "chatgpt_oauth"
    assert [(item["source"], item["status"]) for item in payload["items"]] == [
        ("chatgpt_oauth", "healthy"),
        ("openai_compatible", "failed"),
    ]


def test_chatgpt_account_operations_require_the_oauth_proxy(client, admin_headers) -> None:
    account_response = client.get(f"{ADMIN_BASE}/model-config/chatgpt/account", headers=admin_headers)
    assert account_response.status_code == 200
    assert account_response.json()["connected"] is False
    assert "代理设置" in account_response.json()["error"]

    login_response = client.post(f"{ADMIN_BASE}/model-config/chatgpt/login", headers=admin_headers)
    assert login_response.status_code == 422
    assert "代理设置" in login_response.json()["detail"]
