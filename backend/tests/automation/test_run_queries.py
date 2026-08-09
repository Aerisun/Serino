from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from aerisun.core.time import BEIJING_TZ
from aerisun.domain.automation import repository
from aerisun.domain.automation.runs import get_agent_overview, list_run_collection


def _create_run(
    session,
    *,
    workflow_key: str,
    status: str,
    created_at: datetime,
    execution_mode: str = "live",
    target_id: str | None = None,
    error_message: str | None = None,
):
    run = repository.create_agent_run(
        session,
        workflow_key=workflow_key,
        trigger_kind="manual",
        trigger_event="manual",
        target_type="content" if target_id else None,
        target_id=target_id,
        thread_id=uuid4().hex,
        execution_mode=execution_mode,
    )
    session.flush()
    run.status = status
    run.created_at = created_at
    run.updated_at = created_at
    run.error_message = error_message
    if status in {"running", "awaiting_approval", "completed", "failed", "cancelled"}:
        run.started_at = created_at + timedelta(seconds=1)
    if status in {"completed", "failed", "cancelled"}:
        run.finished_at = created_at + timedelta(seconds=3.5)
    session.flush()
    return run


def test_run_collection_filters_searches_and_uses_stable_cursor(seeded_session) -> None:
    base = datetime(2026, 8, 9, 10, 0, tzinfo=BEIJING_TZ)
    failed = _create_run(
        seeded_session,
        workflow_key="alpha",
        status="failed",
        created_at=base,
        target_id="needle-target",
        error_message="needle failure",
    )
    dry_run = _create_run(
        seeded_session,
        workflow_key="alpha",
        status="completed",
        created_at=base + timedelta(minutes=1),
        execution_mode="dry_run",
    )
    running = _create_run(
        seeded_session,
        workflow_key="beta",
        status="running",
        created_at=base + timedelta(minutes=2),
    )
    queued = _create_run(
        seeded_session,
        workflow_key="alpha",
        status="queued",
        created_at=base + timedelta(minutes=3),
    )
    seeded_session.commit()

    assert [item.id for item in list_run_collection(seeded_session, statuses=["failed"]).items] == [failed.id]
    assert [
        item.id
        for item in list_run_collection(
            seeded_session,
            workflow_key="alpha",
            execution_mode="dry_run",
        ).items
    ] == [dry_run.id]
    assert [item.id for item in list_run_collection(seeded_session, search="needle").items] == [failed.id]
    assert [
        item.id
        for item in list_run_collection(
            seeded_session,
            created_from=base + timedelta(minutes=2),
        ).items
    ] == [queued.id, running.id]

    first_page = list_run_collection(seeded_session, limit=2)
    assert [item.id for item in first_page.items] == [queued.id, running.id]
    assert first_page.total == 4
    assert first_page.has_more is True
    assert first_page.next_cursor

    second_page = list_run_collection(seeded_session, limit=2, cursor=first_page.next_cursor)
    assert [item.id for item in second_page.items] == [dry_run.id, failed.id]
    assert second_page.total == 4
    assert second_page.has_more is False
    assert second_page.next_cursor is None
    assert second_page.items[-1].duration_ms == 2500
    assert second_page.items[-1].can_retry is True
    assert second_page.items[-1].can_cancel is False


def test_agent_overview_uses_database_counts(seeded_session) -> None:
    now = datetime(2026, 8, 9, 12, 0, tzinfo=BEIJING_TZ)
    _create_run(seeded_session, workflow_key="overview", status="queued", created_at=now - timedelta(minutes=5))
    _create_run(seeded_session, workflow_key="overview", status="running", created_at=now - timedelta(minutes=4))
    awaiting = _create_run(
        seeded_session,
        workflow_key="overview",
        status="awaiting_approval",
        created_at=now - timedelta(minutes=3),
    )
    _create_run(seeded_session, workflow_key="overview", status="failed", created_at=now - timedelta(hours=1))
    old_failure = _create_run(
        seeded_session,
        workflow_key="overview",
        status="failed",
        created_at=now - timedelta(days=3),
    )
    old_failure.finished_at = now - timedelta(days=2)
    repository.create_agent_run_approval(
        seeded_session,
        run_id=awaiting.id,
        step_id=None,
        interrupt_id="overview-approval",
        node_key="approval",
        approval_type="manual_review",
    )
    seeded_session.commit()

    overview = get_agent_overview(seeded_session, now=now)

    assert overview.total_run_count == 5
    assert overview.queued_run_count == 1
    assert overview.running_run_count == 1
    assert overview.awaiting_approval_count == 1
    assert overview.pending_approval_count == 1
    assert overview.recent_failed_run_count == 1
    assert overview.enabled_workflow_count >= 1
    assert isinstance(overview.model_ready, bool)


def test_admin_run_collection_and_overview_endpoints(
    seeded_session,
    client,
    admin_headers,
) -> None:
    now = datetime(2026, 8, 9, 12, 0, tzinfo=BEIJING_TZ)
    failed = _create_run(
        seeded_session,
        workflow_key="api-filter",
        status="failed",
        created_at=now,
    )
    seeded_session.commit()

    response = client.get(
        "/api/v1/admin/automation/runs",
        headers=admin_headers,
        params={"status": "failed", "workflow_key": "api-filter", "limit": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == failed.id
    assert payload["items"][0]["duration_ms"] == 2500

    overview_response = client.get("/api/v1/admin/automation/overview", headers=admin_headers)
    assert overview_response.status_code == 200
    assert overview_response.json()["recent_failure_window_hours"] == 24
