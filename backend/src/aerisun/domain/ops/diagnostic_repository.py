from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aerisun.core.base import uuid_str
from aerisun.core.time import shanghai_now
from aerisun.domain.ops.models import SystemDiagnosticState

SYSTEM_DIAGNOSTIC_STATE_ID = "current"
DIAGNOSTIC_RUN_ABANDONED_AFTER = timedelta(minutes=10)
_ACTIVE_STATUSES = ("queued", "running")


def get_diagnostic_state(session: Session) -> SystemDiagnosticState | None:
    return session.get(
        SystemDiagnosticState,
        SYSTEM_DIAGNOSTIC_STATE_ID,
        populate_existing=True,
    )


def _ensure_diagnostic_state(session: Session) -> SystemDiagnosticState:
    state = get_diagnostic_state(session)
    if state is not None:
        return state
    state = SystemDiagnosticState(id=SYSTEM_DIAGNOSTIC_STATE_ID)
    session.add(state)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        state = get_diagnostic_state(session)
        if state is None:  # pragma: no cover - defensive database guard
            raise
        return state
    session.refresh(state)
    return state


def try_queue_diagnostic_run(
    session: Session,
    *,
    trigger_kind: str,
    now: datetime | None = None,
    skip_if_completed_since: datetime | None = None,
) -> tuple[SystemDiagnosticState, bool]:
    state = _ensure_diagnostic_state(session)
    queued_at = now or shanghai_now()
    abandoned_before = queued_at - DIAGNOSTIC_RUN_ABANDONED_AFTER
    run_id = uuid_str()
    conditions = [
        SystemDiagnosticState.id == SYSTEM_DIAGNOSTIC_STATE_ID,
        or_(
            SystemDiagnosticState.execution_status.not_in(_ACTIVE_STATUSES),
            SystemDiagnosticState.started_at.is_(None),
            SystemDiagnosticState.started_at <= abandoned_before,
        ),
    ]
    if skip_if_completed_since is not None:
        conditions.append(
            or_(
                SystemDiagnosticState.completed_at.is_(None),
                SystemDiagnosticState.completed_at < skip_if_completed_since,
            )
        )
    result = session.execute(
        update(SystemDiagnosticState)
        .where(*conditions)
        .values(
            run_id=run_id,
            execution_status="queued",
            trigger_kind=trigger_kind,
            started_at=queued_at,
            last_error=None,
        )
        .execution_options(synchronize_session=False)
    )
    queued = result.rowcount == 1
    session.commit()
    session.refresh(state)
    return state, queued


def claim_diagnostic_run(
    session: Session,
    *,
    run_id: str | None,
    now: datetime | None = None,
) -> bool:
    if not run_id:
        return False
    result = session.execute(
        update(SystemDiagnosticState)
        .where(
            SystemDiagnosticState.id == SYSTEM_DIAGNOSTIC_STATE_ID,
            SystemDiagnosticState.run_id == run_id,
            SystemDiagnosticState.execution_status == "queued",
        )
        .values(execution_status="running", started_at=now or shanghai_now())
        .execution_options(synchronize_session=False)
    )
    claimed = result.rowcount == 1
    session.commit()
    return claimed


def complete_diagnostic_run(
    session: Session,
    *,
    run_id: str | None,
    overall_status: str,
    healthy_count: int,
    warning_count: int,
    failed_count: int,
    skipped_count: int,
    results: list[dict[str, Any]],
    completed_at: datetime | None = None,
    last_error: str | None = None,
) -> bool:
    if not run_id:
        return False
    result = session.execute(
        update(SystemDiagnosticState)
        .where(
            SystemDiagnosticState.id == SYSTEM_DIAGNOSTIC_STATE_ID,
            SystemDiagnosticState.run_id == run_id,
            SystemDiagnosticState.execution_status == "running",
        )
        .values(
            execution_status="completed",
            overall_status=overall_status,
            healthy_count=max(healthy_count, 0),
            warning_count=max(warning_count, 0),
            failed_count=max(failed_count, 0),
            skipped_count=max(skipped_count, 0),
            results_json=results,
            completed_at=completed_at or shanghai_now(),
            last_error=last_error,
        )
        .execution_options(synchronize_session=False)
    )
    completed = result.rowcount == 1
    session.commit()
    return completed
