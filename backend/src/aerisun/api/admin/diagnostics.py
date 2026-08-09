from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.diagnostic_schemas import SystemDiagnosticStateRead
from aerisun.domain.ops.diagnostics import (
    execute_system_diagnostic_run,
    get_system_diagnostic_state,
    queue_system_diagnostic_run,
)

from .deps import get_current_admin

router = APIRouter(prefix="/system/diagnostics", tags=["admin-system"])


@router.get("", response_model=SystemDiagnosticStateRead)
def get_system_diagnostics_state(
    include_items: bool = Query(default=True),
    _admin: AdminUser = Depends(get_current_admin),
) -> SystemDiagnosticStateRead:
    return get_system_diagnostic_state(include_items=include_items)


@router.post(
    "/run",
    response_model=SystemDiagnosticStateRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_system_diagnostics_run(
    background_tasks: BackgroundTasks,
    _admin: AdminUser = Depends(get_current_admin),
) -> SystemDiagnosticStateRead:
    state, queued = queue_system_diagnostic_run(trigger_kind="manual")
    if queued and state.run_id:
        background_tasks.add_task(execute_system_diagnostic_run, state.run_id)
    return state
