from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.domain.ops.diagnostic_repository import get_diagnostic_state

BASE = "/api/v1/admin/system/diagnostics"


def test_system_diagnostics_requires_an_admin_session(client) -> None:
    assert client.get(BASE).status_code == 401
    assert client.post(f"{BASE}/run").status_code == 401


def test_system_diagnostics_returns_unknown_without_creating_a_snapshot(client, admin_headers) -> None:
    response = client.get(BASE, headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "never"
    assert payload["overall_status"] == "unknown"
    assert payload["is_running"] is False
    assert payload["items"] == []
    with get_session_factory()() as session:
        assert get_diagnostic_state(session) is None


def test_manual_diagnostic_returns_accepted_and_reuses_an_active_run(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "aerisun.api.admin.diagnostics.execute_system_diagnostic_run",
        lambda run_id: executed.append(run_id),
    )

    first = client.post(f"{BASE}/run", headers=admin_headers)
    second = client.post(f"{BASE}/run", headers=admin_headers)

    assert first.status_code == 202
    assert second.status_code == 202
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["execution_status"] == "queued"
    assert first_payload["is_running"] is True
    assert second_payload["run_id"] == first_payload["run_id"]
    assert executed == [first_payload["run_id"]]


def test_diagnostic_summary_endpoint_can_omit_items(client, admin_headers, monkeypatch) -> None:
    monkeypatch.setattr(
        "aerisun.api.admin.diagnostics.execute_system_diagnostic_run",
        lambda _run_id: None,
    )
    queued = client.post(f"{BASE}/run", headers=admin_headers)
    assert queued.status_code == 202

    response = client.get(BASE, headers=admin_headers, params={"include_items": "false"})

    assert response.status_code == 200
    assert response.json()["items"] == []
