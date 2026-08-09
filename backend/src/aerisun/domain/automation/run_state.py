"""Central agent-run state machine rules."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from aerisun.core.time import shanghai_now
from aerisun.domain.exceptions import StateConflict

if TYPE_CHECKING:
    from aerisun.domain.automation.models import AgentRun

TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})

LEGAL_RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset({"queued", "awaiting_approval", "interrupted", "completed", "failed", "cancelled"}),
    "awaiting_approval": frozenset({"queued", "running", "completed", "failed", "cancelled"}),
    "interrupted": frozenset({"queued", "running", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class AgentRunCancellationRequested(RuntimeError):
    """Stop graph execution when a run is cancelled at a safe node boundary."""

    def __init__(self, *, run_id: str, node_id: str) -> None:
        self.run_id = run_id
        self.node_id = node_id
        super().__init__(f"Agent run {run_id} was cancelled before node {node_id}")


class AgentRunLeaseLost(RuntimeError):
    """Stop graph execution when the current worker no longer owns the run."""

    def __init__(self, *, run_id: str, node_id: str) -> None:
        self.run_id = run_id
        self.node_id = node_id
        super().__init__(f"Agent run {run_id} lost its lease before node {node_id}")


def is_terminal_run_status(status: str) -> bool:
    return status in TERMINAL_RUN_STATUSES


def is_legal_run_transition(current_status: str, target_status: str) -> bool:
    if current_status == target_status:
        return True
    return target_status in LEGAL_RUN_TRANSITIONS.get(current_status, frozenset())


def ensure_legal_run_transition(current_status: str, target_status: str) -> None:
    if not is_legal_run_transition(current_status, target_status):
        raise StateConflict(f"Agent run cannot transition from {current_status} to {target_status}")


def clear_run_lease(run: AgentRun) -> None:
    run.lease_owner = None
    run.lease_expires_at = None
    run.heartbeat_at = None


def transition_agent_run(
    run: AgentRun,
    target_status: str,
    *,
    at: datetime | None = None,
) -> None:
    ensure_legal_run_transition(run.status, target_status)
    run.status = target_status
    transition_at = at or shanghai_now()
    if target_status == "running":
        run.started_at = run.started_at or transition_at
        run.finished_at = None
    if target_status in TERMINAL_RUN_STATUSES:
        run.finished_at = transition_at
        clear_run_lease(run)
    elif target_status != "running":
        clear_run_lease(run)
