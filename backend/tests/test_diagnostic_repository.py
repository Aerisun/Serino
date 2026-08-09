from __future__ import annotations

from datetime import timedelta

from aerisun.core.time import normalize_shanghai_datetime, shanghai_now
from aerisun.domain.ops.diagnostic_repository import (
    claim_diagnostic_run,
    complete_diagnostic_run,
    get_diagnostic_state,
    try_queue_diagnostic_run,
)


def test_diagnostic_state_is_absent_until_the_first_run_is_queued(seeded_session) -> None:
    assert get_diagnostic_state(seeded_session) is None


def test_queueing_a_run_preserves_the_previous_completed_results(seeded_session) -> None:
    started_at = shanghai_now()
    state, queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="manual",
        now=started_at,
    )
    assert queued is True
    assert claim_diagnostic_run(seeded_session, run_id=state.run_id, now=started_at) is True

    completed_at = started_at + timedelta(seconds=2)
    previous_results = [
        {
            "key": "database",
            "status": "healthy",
            "summary": "数据库连接正常",
            "action_target": "system",
        }
    ]
    complete_diagnostic_run(
        seeded_session,
        run_id=state.run_id,
        overall_status="healthy",
        healthy_count=1,
        warning_count=0,
        failed_count=0,
        skipped_count=0,
        results=previous_results,
        completed_at=completed_at,
    )

    next_state, next_queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="scheduled",
        now=completed_at + timedelta(minutes=1),
    )

    assert next_queued is True
    assert next_state.execution_status == "queued"
    assert next_state.trigger_kind == "scheduled"
    assert next_state.results_json == previous_results
    assert next_state.overall_status == "healthy"
    assert normalize_shanghai_datetime(next_state.completed_at) == completed_at


def test_active_run_is_reused_until_it_becomes_abandoned(seeded_session) -> None:
    started_at = shanghai_now()
    active, queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="manual",
        now=started_at,
    )
    assert queued is True
    active_run_id = active.run_id

    same, duplicate_queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="scheduled",
        now=started_at + timedelta(minutes=9),
    )

    assert duplicate_queued is False
    assert same.run_id == active_run_id
    assert same.trigger_kind == "manual"

    recovered, recovered_queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="startup",
        now=started_at + timedelta(minutes=11),
    )

    assert recovered_queued is True
    assert recovered.run_id != active_run_id
    assert recovered.trigger_kind == "startup"
    assert recovered.execution_status == "queued"


def test_only_the_queued_run_can_be_claimed_and_completed(seeded_session) -> None:
    started_at = shanghai_now()
    state, queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="manual",
        now=started_at,
    )
    assert queued is True

    assert claim_diagnostic_run(seeded_session, run_id="another-run", now=started_at) is False
    assert claim_diagnostic_run(seeded_session, run_id=state.run_id, now=started_at) is True
    assert claim_diagnostic_run(seeded_session, run_id=state.run_id, now=started_at) is False

    complete_diagnostic_run(
        seeded_session,
        run_id=state.run_id,
        overall_status="attention",
        healthy_count=2,
        warning_count=1,
        failed_count=1,
        skipped_count=3,
        results=[{"key": "smtp", "status": "failed"}],
        completed_at=started_at + timedelta(seconds=4),
    )
    completed = get_diagnostic_state(seeded_session)

    assert completed is not None
    assert completed.execution_status == "completed"
    assert completed.overall_status == "attention"
    assert completed.healthy_count == 2
    assert completed.warning_count == 1
    assert completed.failed_count == 1
    assert completed.skipped_count == 3
    assert completed.results_json == [{"key": "smtp", "status": "failed"}]


def test_scheduled_queue_is_skipped_when_a_run_completed_since_its_daily_boundary(
    seeded_session,
) -> None:
    started_at = shanghai_now()
    state, queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="scheduled",
        now=started_at,
    )
    assert queued is True
    assert claim_diagnostic_run(seeded_session, run_id=state.run_id, now=started_at) is True
    completed_at = started_at + timedelta(seconds=1)
    assert (
        complete_diagnostic_run(
            seeded_session,
            run_id=state.run_id,
            overall_status="healthy",
            healthy_count=1,
            warning_count=0,
            failed_count=0,
            skipped_count=0,
            results=[],
            completed_at=completed_at,
        )
        is True
    )

    same_day, duplicate_queued = try_queue_diagnostic_run(
        seeded_session,
        trigger_kind="scheduled",
        now=completed_at + timedelta(seconds=1),
        skip_if_completed_since=started_at,
    )

    assert duplicate_queued is False
    assert same_day.run_id == state.run_id
