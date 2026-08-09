from __future__ import annotations

import json
import stat

import httpx
import pytest

from aerisun.domain.automation import repository, runs
from aerisun.domain.automation.models import WebhookSubscription
from aerisun.domain.automation.runtime import AutomationRuntime, _native_tool_result_message
from aerisun.domain.automation.schemas import (
    AgentModelConfigUpdate,
    AgentWorkflowCreate,
    WebhookSubscriptionCreate,
)
from aerisun.domain.automation.settings import (
    AGENT_MODEL_CONFIG_FLAG_KEY,
    create_agent_workflow,
    get_agent_model_config_resolved,
    update_agent_model_config,
)
from aerisun.domain.automation.webhooks import create_webhook_subscription, list_webhook_subscriptions
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.site_config import repository as site_repository

MODEL_SECRET = "model-secret-sentinel-123456"
WORKFLOW_SECRET = "workflow-secret-sentinel-123456"
HEADER_SECRET = "header-secret-sentinel-123456"


def _webhook_note_workflow(seeded_session, *, key: str, secret: str):
    return create_agent_workflow(
        seeded_session,
        AgentWorkflowCreate(
            key=key,
            name="Security workflow",
            description="Security regression fixture.",
            trigger_bindings=[
                {
                    "id": "incoming",
                    "type": "trigger.webhook",
                    "label": "Incoming",
                    "enabled": True,
                    "config": {"secret": secret},
                }
            ],
            graph={
                "version": 2,
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "nodes": [
                    {
                        "id": "trigger",
                        "type": "trigger.webhook",
                        "label": "Trigger",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                    },
                    {
                        "id": "note",
                        "type": "note",
                        "label": "Note",
                        "position": {"x": 240, "y": 0},
                        "config": {"content": "safe"},
                    },
                ],
                "edges": [
                    {
                        "id": "edge",
                        "source": "trigger",
                        "target": "note",
                        "type": "default",
                        "config": {},
                    }
                ],
            },
        ),
    )


def test_secret_envelope_roundtrip_uses_private_key_file(seeded_session) -> None:
    from aerisun.core.settings import get_settings
    from aerisun.domain.automation.secrets import decrypt_secret, encrypt_secret

    encrypted = encrypt_secret(MODEL_SECRET, purpose="test-model-key")

    assert MODEL_SECRET not in encrypted
    assert decrypt_secret(encrypted, purpose="test-model-key") == MODEL_SECRET
    assert decrypt_secret("legacy-plaintext", purpose="test-model-key") == "legacy-plaintext"
    key_path = get_settings().secrets_dir / "automation-master-key-v1"
    assert key_path.exists()
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


def test_recursive_redaction_masks_headers_urls_and_nested_secrets() -> None:
    from aerisun.core.redaction import redact_sensitive_data

    cyclic: dict[str, object] = {"api_key": MODEL_SECRET}
    cyclic["self"] = cyclic
    payload = {
        "headers": {
            "Authorization": f"Bearer {HEADER_SECRET}",
            "X-Request-ID": "request-1",
        },
        "nested": [{"refresh_token": WORKFLOW_SECRET}],
        "url": f"https://user:{MODEL_SECRET}@example.com/hook?token={WORKFLOW_SECRET}&page=1",
        "cyclic": cyclic,
    }

    redacted = redact_sensitive_data(payload)
    serialized = json.dumps(redacted, ensure_ascii=False)

    assert MODEL_SECRET not in serialized
    assert WORKFLOW_SECRET not in serialized
    assert HEADER_SECRET not in serialized
    assert redacted["headers"]["X-Request-ID"] == "request-1"
    assert "page=1" in redacted["url"]
    assert redacted["cyclic"]["self"] == "[circular]"


def test_model_config_is_encrypted_at_rest_and_never_returned(client, admin_headers) -> None:
    response = client.put(
        "/api/v1/admin/automation/model-config",
        headers=admin_headers,
        json={
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": MODEL_SECRET,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "api_key" not in body["openai_compatible"]
    assert body["openai_compatible"]["api_key_configured"] is True

    from aerisun.core.db import get_session_factory

    with get_session_factory()() as session:
        profile = site_repository.find_site_profile(session)
        assert profile is not None
        stored = dict(profile.feature_flags or {})[AGENT_MODEL_CONFIG_FLAG_KEY]
        assert MODEL_SECRET not in json.dumps(stored)
        assert str(stored["openai_compatible"]["api_key"]).startswith("aerisun:enc:v1:")
        assert get_agent_model_config_resolved(session).openai_compatible.api_key == MODEL_SECRET

    read_response = client.get("/api/v1/admin/automation/model-config", headers=admin_headers)
    assert read_response.status_code == 200
    assert MODEL_SECRET not in read_response.text
    assert "api_key" not in read_response.json()["openai_compatible"]


def test_model_config_omitted_secret_is_preserved_and_can_be_explicitly_cleared(seeded_session) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=True,
            base_url="https://example.com/v1",
            model="test-model",
            api_key=MODEL_SECRET,
        ),
    )

    update_agent_model_config(seeded_session, AgentModelConfigUpdate(model="next-model"))
    assert get_agent_model_config_resolved(seeded_session).openai_compatible.api_key == MODEL_SECRET

    public = update_agent_model_config(seeded_session, AgentModelConfigUpdate(clear_api_key=True))
    assert public.openai_compatible.api_key_configured is False
    assert get_agent_model_config_resolved(seeded_session).openai_compatible.api_key == ""


def test_checkpoint_and_run_snapshot_do_not_contain_model_or_workflow_secrets(
    seeded_session,
    tmp_path,
) -> None:
    update_agent_model_config(
        seeded_session,
        AgentModelConfigUpdate(
            enabled=True,
            base_url="https://example.com/v1",
            model="test-model",
            api_key=MODEL_SECRET,
        ),
    )
    workflow = _webhook_note_workflow(
        seeded_session,
        key="secure_checkpoint_workflow",
        secret=WORKFLOW_SECRET,
    )
    queued = runs.enqueue_workflow_run(
        seeded_session,
        workflow_key=workflow.key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type=None,
        target_id=None,
    )
    checkpoint_path = tmp_path / "secure-checkpoint.sqlite"
    runtime = AutomationRuntime(checkpoint_path=checkpoint_path)
    runtime.start()
    try:
        assert runs.execute_due_runs(seeded_session, runtime, worker_id="security-worker") == 1
    finally:
        runtime.stop()

    persisted = repository.get_agent_run(seeded_session, queued.id)
    assert persisted is not None
    serialized_run = json.dumps(
        {
            "workflow_snapshot": persisted.workflow_snapshot,
            "input_payload": persisted.input_payload,
            "context_payload": persisted.context_payload,
            "result_payload": persisted.result_payload,
        }
    )
    assert MODEL_SECRET not in serialized_run
    assert WORKFLOW_SECRET not in serialized_run
    checkpoint_bytes = checkpoint_path.read_bytes()
    assert MODEL_SECRET.encode() not in checkpoint_bytes
    assert WORKFLOW_SECRET.encode() not in checkpoint_bytes


def test_native_tool_results_are_redacted_before_being_sent_to_model() -> None:
    message = _native_tool_result_message(
        "tool-1",
        {
            "api_key": MODEL_SECRET,
            "headers": {"Authorization": f"Bearer {HEADER_SECRET}"},
            "safe": "visible",
        },
    )

    assert MODEL_SECRET not in message["content"]
    assert HEADER_SECRET not in message["content"]
    assert "visible" in message["content"]


def test_webhook_subscription_secrets_are_encrypted_and_public_reads_are_masked(seeded_session) -> None:
    created = create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Secure webhook",
            target_url=f"https://hooks.example.com/incoming?token={WORKFLOW_SECRET}",
            event_types=["test.event"],
            secret=MODEL_SECRET,
            headers={"Authorization": f"Bearer {HEADER_SECRET}", "X-Request-ID": "request-1"},
        ),
    )

    stored = seeded_session.get(WebhookSubscription, created.id)
    assert stored is not None
    assert MODEL_SECRET not in str(stored.secret)
    assert WORKFLOW_SECRET not in stored.target_url
    assert HEADER_SECRET not in json.dumps(stored.headers)

    public = list_webhook_subscriptions(seeded_session)[0]
    serialized = public.model_dump_json()
    assert MODEL_SECRET not in serialized
    assert WORKFLOW_SECRET not in serialized
    assert HEADER_SECRET not in serialized
    assert public.secret_configured is True
    assert public.headers["X-Request-ID"] == "request-1"


def test_webhook_dispatch_decrypts_destination_and_headers(seeded_session, monkeypatch) -> None:
    from aerisun.domain.automation.models import AutomationEvent
    from aerisun.domain.automation.webhooks import dispatch_due_webhooks

    created = create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Dispatch webhook",
            target_url=f"https://hooks.example.com/incoming?token={WORKFLOW_SECRET}",
            event_types=["test.event"],
            secret=MODEL_SECRET,
            headers={"Authorization": f"Bearer {HEADER_SECRET}"},
        ),
    )
    subscription = seeded_session.get(WebhookSubscription, created.id)
    assert subscription is not None
    repository.create_webhook_delivery(
        seeded_session,
        subscription=subscription,
        event=AutomationEvent(
            event_type="test.event",
            event_id="event-1",
            target_type="test",
            target_id="target-1",
            payload={"safe": True},
        ),
    )
    seeded_session.commit()
    observed: dict[str, object] = {}

    def fake_post(url, *, json, headers, timeout, **kwargs):
        observed.update({"url": url, "headers": headers, "json": json, "timeout": timeout, "kwargs": kwargs})
        return httpx.Response(200, text="ok")

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fake_post)

    assert dispatch_due_webhooks(seeded_session) == 1
    assert WORKFLOW_SECRET in str(observed["url"])
    assert observed["headers"]["Authorization"] == f"Bearer {HEADER_SECRET}"


@pytest.mark.parametrize(
    "target_url",
    [
        "file:///etc/passwd",
        "http://localhost:8080/hook",
        "http://127.0.0.1:8080/hook",
        "http://[::1]:8080/hook",
        "http://169.254.169.254/latest/meta-data",
        "https://user:password@example.com/hook",
        "https://example.com:22/hook",
    ],
)
def test_webhook_destination_rejects_unsafe_targets(seeded_session, target_url: str) -> None:
    with pytest.raises(ValidationError, match="Webhook target URL"):
        create_webhook_subscription(
            seeded_session,
            WebhookSubscriptionCreate(
                name="Unsafe webhook",
                target_url=target_url,
                event_types=["test.event"],
            ),
        )


def test_webhook_private_destination_requires_explicit_opt_in(seeded_session) -> None:
    created = create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Private webhook",
            target_url="http://127.0.0.1:8080/hook",
            event_types=["test.event"],
            allow_private_network=True,
        ),
    )

    assert created.allow_private_network is True


def test_webhook_dispatch_revalidates_stored_destination(seeded_session, monkeypatch) -> None:
    from aerisun.domain.automation.models import AutomationEvent
    from aerisun.domain.automation.secrets import encrypt_secret
    from aerisun.domain.automation.webhooks import (
        WEBHOOK_DESTINATION_PURPOSE,
        dispatch_due_webhooks,
    )

    created = create_webhook_subscription(
        seeded_session,
        WebhookSubscriptionCreate(
            name="Revalidated webhook",
            target_url="https://example.com/hook",
            event_types=["test.event"],
        ),
    )
    subscription = seeded_session.get(WebhookSubscription, created.id)
    assert subscription is not None
    subscription.target_url = encrypt_secret(
        "http://169.254.169.254/latest/meta-data",
        purpose=WEBHOOK_DESTINATION_PURPOSE,
    )
    repository.create_webhook_delivery(
        seeded_session,
        subscription=subscription,
        event=AutomationEvent(
            event_type="test.event",
            event_id="event-private-target",
            target_type="test",
            target_id="target-1",
            payload={"safe": True},
        ),
    )
    seeded_session.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("unsafe webhook destination reached the HTTP client")

    monkeypatch.setattr("aerisun.domain.automation.webhooks.httpx.post", fail_if_called)

    assert dispatch_due_webhooks(seeded_session) == 1
    delivery = repository.list_webhook_deliveries(seeded_session)[0]
    assert delivery.status == "dead_lettered"
    assert "target URL" in str(delivery.last_error)


def test_inbound_webhook_requires_configured_secret(seeded_session) -> None:
    workflow = _webhook_note_workflow(
        seeded_session,
        key="missing_webhook_secret_workflow",
        secret="",
    )

    with pytest.raises(ValidationError, match="secret"):
        runs.trigger_webhook_workflow(
            seeded_session,
            object(),
            workflow_key=workflow.key,
            binding_id="incoming",
            provided_secret="",
            body={"event_id": "event-1"},
        )


def test_inbound_webhook_rejects_short_secret(seeded_session) -> None:
    workflow = _webhook_note_workflow(
        seeded_session,
        key="short_webhook_secret_workflow",
        secret="short-secret",
    )

    with pytest.raises(ValidationError, match="at least 16"):
        runs.trigger_webhook_workflow(
            seeded_session,
            object(),
            workflow_key=workflow.key,
            binding_id="incoming",
            provided_secret="short-secret",
            body={"event_id": "event-1"},
        )
