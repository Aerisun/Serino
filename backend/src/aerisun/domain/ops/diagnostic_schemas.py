from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DiagnosticItemStatus = Literal["healthy", "warning", "failed", "skipped"]
DiagnosticOverallStatus = Literal["unknown", "healthy", "attention"]
DiagnosticExecutionStatus = Literal["never", "queued", "running", "completed"]
DiagnosticTriggerKind = Literal["manual", "scheduled", "startup"]
DiagnosticActionTarget = Literal[
    "system",
    "model_api",
    "smtp",
    "proxy",
    "object_storage",
    "object_storage_sync",
    "backup_settings",
    "backup_runs",
    "mcp",
    "service_forwards",
]


class SystemDiagnosticItemRead(BaseModel):
    key: str
    status: DiagnosticItemStatus
    summary: str
    summary_key: str | None = None
    summary_params: dict[str, str | int] = Field(default_factory=dict)
    detail: str | None = None
    detail_key: str | None = None
    detail_params: dict[str, str | int] = Field(default_factory=dict)
    action_target: DiagnosticActionTarget
    duration_ms: int | None = Field(default=None, ge=0)
    checked_at: datetime | None = None


class SystemDiagnosticStateRead(BaseModel):
    execution_status: DiagnosticExecutionStatus = "never"
    overall_status: DiagnosticOverallStatus = "unknown"
    trigger_kind: DiagnosticTriggerKind | None = None
    run_id: str | None = None
    is_running: bool = False
    is_stale: bool = False
    healthy_count: int = 0
    warning_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    issue_count: int = 0
    items: list[SystemDiagnosticItemRead] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None
    last_error_key: str | None = None
