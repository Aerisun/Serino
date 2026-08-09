"""Run scheduling, execution, and querying."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import socket
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64DecodeError
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import ALL_SCOPES
from aerisun.core.db import get_session_factory
from aerisun.core.redaction import safe_exception_detail
from aerisun.core.time import BEIJING_TZ, normalize_shanghai_datetime, shanghai_now
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation._helpers import fallback_workflow_config
from aerisun.domain.automation.models import AgentRun
from aerisun.domain.automation.run_state import (
    LEGAL_RUN_TRANSITIONS,
    AgentRunCancellationRequested,
    AgentRunLeaseLost,
    is_terminal_run_status,
    transition_agent_run,
)
from aerisun.domain.automation.runtime import RUNTIME_STATE_SECRET_PURPOSE, AutomationRuntime
from aerisun.domain.automation.schemas import (
    AgentOverviewRead,
    AgentRunCollectionRead,
    AgentRunRead,
    AgentRunStepRead,
    AgentWorkflowRead,
    AgentWorkflowRunCreateRead,
    AgentWorkflowRunCreateWrite,
    AgentWorkflowWebhookTriggerRead,
)
from aerisun.domain.automation.secrets import protect_sensitive_data, reveal_sensitive_data
from aerisun.domain.automation.settings import (
    agent_model_runtime_config,
    find_agent_workflow,
    find_workflow_trigger_binding,
    get_agent_model_config_resolved,
    get_agent_workflow,
    list_agent_workflows,
    list_workflow_bindings_by_type,
)
from aerisun.domain.automation.validation import compile_workflow
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError

if TYPE_CHECKING:
    from aerisun.domain.automation.models import AutomationEvent

logger = logging.getLogger(__name__)

DEFAULT_RUN_LEASE_SECONDS = 600
MIN_WORKFLOW_WEBHOOK_SECRET_LENGTH = 16
_PROCESS_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class RunPrincipal:
    principal_type: str
    principal_id: str | None = None
    scopes: tuple[str, ...] = ()


def full_access_run_principal(principal_type: str, principal_id: str | None = None) -> RunPrincipal:
    return RunPrincipal(
        principal_type=principal_type,
        principal_id=principal_id,
        scopes=tuple(ALL_SCOPES),
    )


def _normalize_run_principal(principal: RunPrincipal | None) -> RunPrincipal:
    effective = principal or full_access_run_principal("system")
    principal_type = str(effective.principal_type or "").strip().lower()
    principal_id = str(effective.principal_id or "").strip() or None
    scopes = tuple(sorted({str(item).strip() for item in effective.scopes if str(item).strip()}))
    if not principal_type or len(principal_type) > 40:
        raise ValidationError("Agent run principal type must be between 1 and 40 characters")
    if principal_id is not None and len(principal_id) > 120:
        raise ValidationError("Agent run principal id must be at most 120 characters")
    if len(scopes) > 100 or any(len(scope) > 120 for scope in scopes):
        raise ValidationError("Agent run authorization scopes are invalid")
    return RunPrincipal(
        principal_type=principal_type,
        principal_id=principal_id,
        scopes=scopes,
    )


def _workflow_fingerprint(workflow_snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(
        workflow_snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _workflow_max_attempts(workflow_snapshot: dict[str, Any]) -> int:
    runtime_policy = dict(workflow_snapshot.get("runtime_policy") or {})
    retry_policy = dict(runtime_policy.get("retry_policy") or {})
    try:
        configured = int(retry_policy.get("max_attempts") or 3)
    except (TypeError, ValueError):
        configured = 3
    return min(max(configured, 1), 100)


def enqueue_workflow_run(
    session: Session,
    *,
    workflow_key: str,
    trigger_kind: str,
    trigger_event: str | None,
    target_type: str | None,
    target_id: str | None,
    input_payload: dict[str, Any] | None = None,
    context_payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    execution_mode: str = "live",
    principal: RunPrincipal | None = None,
    autocommit: bool = True,
) -> AgentRunRead:
    normalized_idempotency_key = str(idempotency_key or "").strip() or None
    if normalized_idempotency_key is not None and len(normalized_idempotency_key) > 255:
        raise ValidationError("Agent run idempotency key must be at most 255 characters")
    if execution_mode not in {"live", "dry_run"}:
        raise ValidationError("Unsupported Agent run execution mode")
    if normalized_idempotency_key is not None:
        existing = repo.get_agent_run_by_idempotency_key(
            session,
            workflow_key=workflow_key,
            idempotency_key=normalized_idempotency_key,
        )
        if existing is not None:
            return AgentRunRead.model_validate(existing)

    workflow = get_agent_workflow(session, workflow_key)
    effective_principal = _normalize_run_principal(principal)
    plaintext_workflow_snapshot = workflow.model_dump(mode="json")
    workflow_snapshot = protect_sensitive_data(
        plaintext_workflow_snapshot,
        purpose=RUNTIME_STATE_SECRET_PURPOSE,
    )

    def create_run() -> AgentRun:
        return repo.create_agent_run(
            session,
            workflow_key=workflow_key,
            trigger_kind=trigger_kind,
            trigger_event=trigger_event,
            target_type=target_type,
            target_id=target_id,
            input_payload=input_payload,
            context_payload=context_payload,
            thread_id=uuid4().hex,
            execution_mode=execution_mode,
            workflow_snapshot=workflow_snapshot,
            workflow_fingerprint=_workflow_fingerprint(plaintext_workflow_snapshot),
            idempotency_key=normalized_idempotency_key,
            requested_by_type=effective_principal.principal_type,
            requested_by_id=effective_principal.principal_id,
            authorization_scopes=list(effective_principal.scopes),
            available_at=shanghai_now(),
            max_attempts=_workflow_max_attempts(workflow_snapshot),
        )

    try:
        if normalized_idempotency_key is not None:
            with session.begin_nested():
                run = create_run()
                session.flush()
        else:
            run = create_run()
            session.flush()
    except IntegrityError:
        if normalized_idempotency_key is None:
            raise
        existing = repo.get_agent_run_by_idempotency_key(
            session,
            workflow_key=workflow_key,
            idempotency_key=normalized_idempotency_key,
        )
        if existing is None:
            raise
        return AgentRunRead.model_validate(existing)

    if autocommit:
        session.commit()
        session.refresh(run)
    return AgentRunRead.model_validate(run)


def list_runs(session: Session) -> list[AgentRunRead]:
    return [AgentRunRead.model_validate(item) for item in repo.list_agent_runs(session)]


def _encode_run_cursor(run: AgentRun) -> str:
    payload = {
        "v": 1,
        "created_at": normalize_shanghai_datetime(run.created_at).isoformat(),
        "id": run.id,
    }
    encoded = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    return encoded.rstrip("=")


def _decode_run_cursor(cursor: str) -> tuple[datetime, str]:
    normalized = str(cursor or "").strip()
    if not normalized or len(normalized) > 512:
        raise ValidationError("Invalid Agent run cursor")
    try:
        raw = urlsafe_b64decode(normalized + ("=" * (-len(normalized) % 4)))
        payload = json.loads(raw.decode())
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise ValueError("unsupported cursor version")
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        run_id = str(payload["id"]).strip()
        if not run_id or len(run_id) > 64:
            raise ValueError("invalid run id")
    except (Base64DecodeError, KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid Agent run cursor") from exc
    return normalize_shanghai_datetime(created_at), run_id


def list_run_collection(
    session: Session,
    *,
    statuses: list[str] | None = None,
    workflow_key: str | None = None,
    execution_mode: str | None = None,
    search: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    cursor: str | None = None,
    limit: int = 25,
) -> AgentRunCollectionRead:
    normalized_statuses = sorted({str(item).strip() for item in statuses or [] if str(item).strip()})
    unknown_statuses = sorted(set(normalized_statuses) - set(LEGAL_RUN_TRANSITIONS))
    if unknown_statuses:
        raise ValidationError(f"Unsupported Agent run status: {', '.join(unknown_statuses)}")
    normalized_workflow_key = str(workflow_key or "").strip() or None
    normalized_mode = str(execution_mode or "").strip() or None
    if normalized_mode not in {None, "live", "dry_run"}:
        raise ValidationError("Unsupported Agent run execution mode")
    normalized_search = str(search or "").strip() or None
    if normalized_search is not None and len(normalized_search) > 200:
        raise ValidationError("Agent run search must be at most 200 characters")
    effective_limit = int(limit)
    if effective_limit < 1 or effective_limit > 100:
        raise ValidationError("Agent run page size must be between 1 and 100")
    normalized_from = normalize_shanghai_datetime(created_from) if created_from is not None else None
    normalized_to = normalize_shanghai_datetime(created_to) if created_to is not None else None
    if normalized_from is not None and normalized_to is not None and normalized_from > normalized_to:
        raise ValidationError("Agent run created_from must not be later than created_to")
    cursor_created_at = None
    cursor_id = None
    if cursor:
        cursor_created_at, cursor_id = _decode_run_cursor(cursor)

    rows, total, has_more = repo.query_agent_runs(
        session,
        statuses=normalized_statuses,
        workflow_key=normalized_workflow_key,
        execution_mode=normalized_mode,
        search=normalized_search,
        created_from=normalized_from,
        created_to=normalized_to,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
        limit=effective_limit,
    )
    return AgentRunCollectionRead(
        items=[AgentRunRead.model_validate(item) for item in rows],
        total=total,
        limit=effective_limit,
        has_more=has_more,
        next_cursor=_encode_run_cursor(rows[-1]) if has_more and rows else None,
    )


def get_agent_overview(
    session: Session,
    *,
    now: datetime | None = None,
    recent_failure_window_hours: int = 24,
) -> AgentOverviewRead:
    window_hours = min(max(int(recent_failure_window_hours), 1), 24 * 30)
    generated_at = normalize_shanghai_datetime(now or shanghai_now())
    status_counts = repo.agent_run_status_counts(session)
    workflows = list_agent_workflows(session)
    model_config = get_agent_model_config_resolved(session)
    return AgentOverviewRead(
        model_ready=model_config.is_ready,
        total_workflow_count=len(workflows),
        enabled_workflow_count=sum(1 for workflow in workflows if workflow.enabled),
        total_run_count=sum(status_counts.values()),
        queued_run_count=status_counts.get("queued", 0),
        running_run_count=status_counts.get("running", 0),
        awaiting_approval_count=status_counts.get("awaiting_approval", 0),
        pending_approval_count=repo.count_pending_agent_run_approvals(session),
        recent_failed_run_count=repo.count_recent_failed_agent_runs(
            session,
            since=generated_at - timedelta(hours=window_hours),
        ),
        recent_failure_window_hours=window_hours,
        generated_at=generated_at,
    )


def get_run_detail(session: Session, run_id: str) -> tuple[AgentRunRead, list[AgentRunStepRead]]:
    run = repo.get_agent_run(session, run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    steps = repo.list_agent_run_steps(session, run_id=run_id)
    return AgentRunRead.model_validate(run), [AgentRunStepRead.model_validate(step) for step in steps]


def cancel_workflow_run(session: Session, *, run_id: str) -> AgentRunRead:
    run = repo.get_agent_run(session, run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    if is_terminal_run_status(run.status):
        raise StateConflict("A terminal Agent run cannot be cancelled")

    now = shanghai_now()
    run.cancel_requested_at = run.cancel_requested_at or now
    if run.status != "running":
        transition_agent_run(run, "cancelled", at=now)
        run.result_payload = {
            "cancelled": True,
            "reason": "user_requested",
            "workflow_key": run.workflow_key,
        }
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=_next_run_sequence_no(session, run.id),
            node_key="workflow_cancel",
            step_kind="run_cancelled",
            status="cancelled",
            narrative="工作流已按请求取消。",
            output_payload=run.result_payload,
            finished_at=now,
        )
    session.commit()
    session.refresh(run)
    return AgentRunRead.model_validate(run)


def cancel_run_at_node_boundary(session: Session, *, run: AgentRun) -> bool:
    if is_terminal_run_status(run.status):
        return run.status == "cancelled"
    session.refresh(run, attribute_names=["status", "cancel_requested_at"])
    if is_terminal_run_status(run.status):
        return run.status == "cancelled"
    if run.cancel_requested_at is None:
        return False
    now = shanghai_now()
    transition_agent_run(run, "cancelled", at=now)
    run.result_payload = {
        "cancelled": True,
        "reason": "user_requested",
        "workflow_key": run.workflow_key,
    }
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=_next_run_sequence_no(session, run.id),
        node_key="workflow_cancel",
        step_kind="run_cancelled",
        status="cancelled",
        narrative="工作流在安全节点边界响应取消请求。",
        output_payload=run.result_payload,
        finished_at=now,
    )
    session.flush()
    return True


def retry_workflow_run(session: Session, *, run_id: str) -> AgentRunRead:
    source = repo.get_agent_run(session, run_id)
    if source is None:
        raise ResourceNotFound("Agent run not found")
    if not is_terminal_run_status(source.status):
        raise StateConflict("Only a terminal Agent run can be retried")

    workflow_snapshot = dict(source.workflow_snapshot or {})
    if not workflow_snapshot:
        workflow_snapshot = dict((source.input_payload or {}).get("workflow_config_snapshot") or {})
    if not workflow_snapshot:
        fallback = find_agent_workflow(session, source.workflow_key) or fallback_workflow_config(source)
        workflow_snapshot = _workflow_snapshot_payload(fallback)

    retried = repo.create_agent_run(
        session,
        workflow_key=source.workflow_key,
        trigger_kind=source.trigger_kind,
        trigger_event=source.trigger_event,
        target_type=source.target_type,
        target_id=source.target_id,
        input_payload=deepcopy(source.input_payload or {}),
        context_payload=deepcopy(source.context_payload or {}),
        thread_id=uuid4().hex,
        execution_mode=source.execution_mode,
        workflow_snapshot=deepcopy(workflow_snapshot),
        workflow_fingerprint=source.workflow_fingerprint or _workflow_fingerprint(workflow_snapshot),
        available_at=shanghai_now(),
        max_attempts=source.max_attempts,
        retry_of_run_id=source.id,
        requested_by_type=source.requested_by_type,
        requested_by_id=source.requested_by_id,
        authorization_scopes=list(source.authorization_scopes or []),
    )
    session.commit()
    session.refresh(retried)
    return AgentRunRead.model_validate(retried)


def _select_trigger_binding(
    workflow: AgentWorkflowRead,
    payload: AgentWorkflowRunCreateWrite | None,
    *,
    preferred_type: str | None = None,
):
    binding_id = str((payload.trigger_binding_id if payload else "") or "").strip()
    if binding_id:
        return next((item for item in workflow.trigger_bindings if item.id == binding_id and item.enabled), None)
    if preferred_type:
        binding = next(
            (item for item in workflow.trigger_bindings if item.enabled and item.type == preferred_type), None
        )
        if binding is not None:
            return binding
    return next((item for item in workflow.trigger_bindings if item.enabled), None)


def _run_trigger_event(binding, payload: AgentWorkflowRunCreateWrite | None) -> str:
    if payload and payload.trigger_event:
        return payload.trigger_event
    config = dict(binding.config or {}) if binding is not None else {}
    return str(config.get("event_type") or config.get("path") or (binding.type if binding is not None else "manual"))


def _run_target_type(binding, payload: AgentWorkflowRunCreateWrite | None) -> str | None:
    if payload and payload.target_type:
        return payload.target_type
    config = dict(binding.config or {}) if binding is not None else {}
    return str(config.get("target_type") or "").strip() or None


def create_workflow_run(
    session: Session,
    runtime: AutomationRuntime,
    *,
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite,
    trigger_kind: str = "manual",
    principal: RunPrincipal | None = None,
) -> AgentWorkflowRunCreateRead:
    workflow = get_agent_workflow(session, workflow_key)
    validation = compile_workflow(workflow.model_dump(mode="json"), session=session)
    if not validation.ok:
        raise ValidationError("Workflow validation failed")
    binding = _select_trigger_binding(
        workflow, payload, preferred_type=f"trigger.{trigger_kind}" if trigger_kind else None
    )
    queued = enqueue_workflow_run(
        session,
        workflow_key=workflow.key,
        trigger_kind=trigger_kind,
        trigger_event=_run_trigger_event(binding, payload),
        target_type=_run_target_type(binding, payload),
        target_id=payload.target_id,
        input_payload={
            **dict(payload.input_payload or {}),
            "trigger_binding_id": binding.id if binding is not None else None,
        },
        context_payload=dict(payload.context_payload or {}),
        idempotency_key=payload.idempotency_key,
        execution_mode=payload.execution_mode,
        principal=principal,
        autocommit=True,
    )
    if payload.execute_immediately:
        execute_run_now(session, runtime, run_id=queued.id)
        session.expire_all()
    run, steps = get_run_detail(session, queued.id)
    return AgentWorkflowRunCreateRead(run=run, steps=steps, validation=validation)


def test_workflow_run(
    session: Session,
    runtime: AutomationRuntime,
    *,
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite,
    principal: RunPrincipal | None = None,
) -> AgentWorkflowRunCreateRead:
    dry_run_payload = payload.model_copy(update={"execution_mode": "dry_run"})
    return create_workflow_run(
        session,
        runtime,
        workflow_key=workflow_key,
        payload=dry_run_payload,
        trigger_kind="manual",
        principal=principal,
    )


def trigger_webhook_workflow(
    session: Session,
    runtime: AutomationRuntime,
    *,
    workflow_key: str,
    binding_id: str,
    provided_secret: str,
    body: dict[str, Any] | None,
    idempotency_key: str | None = None,
) -> AgentWorkflowWebhookTriggerRead:
    workflow, binding = find_workflow_trigger_binding(session, workflow_key=workflow_key, binding_id=binding_id)
    config = dict(binding.config or {})
    expected_secret = str(config.get("secret") or "").strip()
    if len(expected_secret) < MIN_WORKFLOW_WEBHOOK_SECRET_LENGTH:
        raise ValidationError(
            f"Webhook trigger secret must be at least {MIN_WORKFLOW_WEBHOOK_SECRET_LENGTH} characters"
        )
    if not hmac.compare_digest(provided_secret.encode("utf-8"), expected_secret.encode("utf-8")):
        raise ValidationError("Invalid webhook trigger secret")
    normalized_idempotency_key = str(idempotency_key or "").strip() or None
    if normalized_idempotency_key is None:
        for stable_id_field in ("event_id", "delivery_id"):
            stable_id = (body or {}).get(stable_id_field)
            if stable_id is None or isinstance(stable_id, (dict, list)):
                continue
            normalized_stable_id = str(stable_id).strip()
            if not normalized_stable_id:
                continue
            stable_id_fingerprint = hashlib.sha256(normalized_stable_id.encode("utf-8")).hexdigest()
            normalized_idempotency_key = f"webhook-{stable_id_field}:{binding.id}:{stable_id_fingerprint}"
            break
    payload = AgentWorkflowRunCreateWrite(
        trigger_binding_id=binding.id,
        trigger_event=str(config.get("event_type") or config.get("path") or f"webhook:{binding.id}"),
        target_type=str(config.get("target_type") or "").strip() or None,
        target_id=str((body or {}).get("target_id") or ""),
        context_payload=dict(body or {}),
        input_payload={"trigger_binding_id": binding.id},
        idempotency_key=normalized_idempotency_key,
        execute_immediately=True,
    )
    created = create_workflow_run(
        session,
        runtime,
        workflow_key=workflow.key,
        payload=payload,
        trigger_kind="webhook",
        principal=full_access_run_principal(
            "workflow_webhook",
            f"{workflow.key}:{binding.id}",
        ),
    )
    return AgentWorkflowWebhookTriggerRead(
        ok=True,
        run=created.run,
        accepted=True,
        summary="Webhook trigger accepted.",
    )


# ---------------------------------------------------------------------------
# Run execution internals
# ---------------------------------------------------------------------------


def _mark_run_cancelled(
    session: Session,
    *,
    run: AgentRun,
    sequence_no: int,
    narrative: str,
    reason: str,
) -> None:
    transition_agent_run(run, "cancelled")
    run.result_payload = {"skipped": True, "reason": reason, "workflow_key": run.workflow_key}
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=sequence_no,
        node_key="workflow_dispatch",
        step_kind="node_cancelled",
        status="cancelled",
        narrative=narrative,
        output_payload=run.result_payload,
        finished_at=shanghai_now(),
    )


def _mark_run_failed(
    session: Session,
    *,
    run: AgentRun,
    sequence_no: int,
    narrative: str,
    error_code: str,
    error_message: str,
) -> None:
    transition_agent_run(run, "failed")
    run.error_code = error_code
    run.error_message = error_message
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=sequence_no,
        node_key="workflow_dispatch",
        step_kind="node_failed",
        status="failed",
        narrative=narrative,
        error_payload={"error_code": run.error_code, "error_message": run.error_message},
        finished_at=shanghai_now(),
    )


def _make_node_boundary_hook(
    *,
    run_id: str,
    worker_id: str,
    lease_seconds: int,
) -> Callable[[str], None]:
    def guard(node_id: str) -> None:
        with get_session_factory()() as boundary_session:
            if repo.heartbeat_agent_run(
                boundary_session,
                run_id=run_id,
                worker_id=worker_id,
                now=shanghai_now(),
                lease_seconds=lease_seconds,
                reject_cancel_requested=True,
            ):
                boundary_session.commit()
                return

            current = (
                boundary_session.query(
                    AgentRun.status,
                    AgentRun.lease_owner,
                    AgentRun.cancel_requested_at,
                )
                .filter(AgentRun.id == run_id)
                .one_or_none()
            )
            if (
                current is not None
                and current.status == "running"
                and current.lease_owner == worker_id
                and current.cancel_requested_at is not None
            ):
                raise AgentRunCancellationRequested(run_id=run_id, node_id=node_id)
            raise AgentRunLeaseLost(run_id=run_id, node_id=node_id)

    return guard


def _safe_rollback_runtime_session(session: Session, *, run_id: str) -> None:
    try:
        session.rollback()
    except Exception:
        logger.exception("Failed to roll back invalid Agent run session", extra={"run_id": run_id})


def _persist_runtime_cancellation(*, run_id: str, worker_id: str) -> bool:
    try:
        with get_session_factory()() as fresh_session:
            run = repo.get_agent_run(fresh_session, run_id)
            if run is None:
                logger.error("Agent run disappeared while persisting cancellation", extra={"run_id": run_id})
                return False
            if is_terminal_run_status(run.status):
                return run.status == "cancelled"
            if run.status != "running" or run.lease_owner != worker_id:
                logger.warning(
                    "Agent run ownership changed before cancellation persistence",
                    extra={"run_id": run_id, "worker_id": worker_id},
                )
                return False
            if not cancel_run_at_node_boundary(fresh_session, run=run):
                return False
            fresh_session.commit()
            return True
    except Exception:
        logger.exception("Failed to persist Agent run cancellation", extra={"run_id": run_id})
        return False


def _is_retryable_runtime_error(error: BaseException) -> bool:
    if isinstance(error, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError, OperationalError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return False


def _retry_delay_seconds(run: AgentRun) -> float:
    workflow_snapshot = dict(run.workflow_snapshot or {})
    runtime_policy = dict(workflow_snapshot.get("runtime_policy") or {})
    retry_policy = dict(runtime_policy.get("retry_policy") or {})

    def number(name: str, default: float, *, minimum: float, maximum: float) -> float:
        try:
            value = float(retry_policy.get(name, default))
        except (TypeError, ValueError):
            value = default
        return min(max(value, minimum), maximum)

    initial_seconds = number("initial_seconds", 5, minimum=0, maximum=3600)
    multiplier = number("multiplier", 2, minimum=1, maximum=10)
    max_seconds = number("max_seconds", 300, minimum=0, maximum=86400)
    jitter_ratio = number("jitter_ratio", 0.1, minimum=0, maximum=0.5)
    base_delay = min(initial_seconds * (multiplier ** max(run.attempt_count - 1, 0)), max_seconds)
    if base_delay <= 0 or jitter_ratio <= 0:
        return max(base_delay, 0)
    seed = hashlib.sha256(f"{run.id}:{run.attempt_count}".encode()).digest()
    unit = int.from_bytes(seed[:8], "big") / ((1 << 64) - 1)
    jittered = base_delay * (1 + jitter_ratio * ((unit * 2) - 1))
    return min(max(jittered, 0), max_seconds)


def _schedule_runtime_retry(
    session: Session,
    *,
    run: AgentRun,
    error_code: str,
    error_message: str,
) -> None:
    delay_seconds = _retry_delay_seconds(run)
    transition_agent_run(run, "queued")
    run.available_at = shanghai_now() + timedelta(seconds=delay_seconds)
    run.error_code = error_code
    run.error_message = error_message
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=_next_run_sequence_no(session, run.id),
        node_key="workflow_retry",
        step_kind="run_retry_scheduled",
        status="queued",
        narrative=f"检测到可重试的瞬态错误，已安排第 {run.attempt_count + 1} 次尝试。",
        error_payload={
            "error_code": error_code,
            "error_message": error_message,
            "retry_in_seconds": delay_seconds,
        },
        finished_at=shanghai_now(),
    )


def _persist_runtime_failure(
    *,
    run_id: str,
    worker_id: str,
    error_code: str,
    error_message: str,
    retryable: bool,
) -> bool:
    try:
        with get_session_factory()() as fresh_session:
            run = repo.get_agent_run(fresh_session, run_id)
            if run is None:
                logger.error("Agent run disappeared while persisting failure", extra={"run_id": run_id})
                return False
            if is_terminal_run_status(run.status):
                return run.status in {"failed", "cancelled"}
            if run.status != "running" or run.lease_owner != worker_id:
                logger.warning(
                    "Agent run ownership changed before failure persistence",
                    extra={"run_id": run_id, "worker_id": worker_id},
                )
                return False
            if run.cancel_requested_at is not None:
                if not cancel_run_at_node_boundary(fresh_session, run=run):
                    return False
            elif retryable and run.attempt_count < run.max_attempts:
                _schedule_runtime_retry(
                    fresh_session,
                    run=run,
                    error_code=error_code,
                    error_message=error_message,
                )
            else:
                _mark_run_failed(
                    fresh_session,
                    run=run,
                    sequence_no=_next_run_sequence_no(fresh_session, run.id),
                    narrative="工作流执行失败。",
                    error_code=error_code,
                    error_message=error_message,
                )
            fresh_session.commit()
            return True
    except Exception:
        logger.exception("Failed to persist Agent run failure", extra={"run_id": run_id})
        return False


def _extract_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result_payload")
    return payload if isinstance(payload, dict) else result


def _extract_execution_trace(result: dict[str, Any], snapshot: Any | None = None) -> list[dict[str, Any]]:
    payload = result.get("execution_trace")
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    snapshot_values = getattr(snapshot, "values", None)
    if isinstance(snapshot_values, dict):
        trace = snapshot_values.get("execution_trace")
        if isinstance(trace, list):
            return [dict(item) for item in trace if isinstance(item, dict)]
    return []


def _next_run_sequence_no(session: Session, run_id: str) -> int:
    session.flush()
    steps = repo.list_agent_run_steps(session, run_id=run_id)
    return (steps[-1].sequence_no if steps else 0) + 1


def _persist_graph_trace_steps(session: Session, run: AgentRun, trace: list[dict[str, Any]]) -> None:
    existing_steps = repo.list_agent_run_steps(session, run_id=run.id)
    persisted_count = len([item for item in existing_steps if item.step_kind == "graph_node_completed"])
    next_sequence = (existing_steps[-1].sequence_no if existing_steps else 0) + 1
    for entry in trace[persisted_count:]:
        finished_at_raw = entry.get("finished_at")
        finished_at = None
        if isinstance(finished_at_raw, str):
            try:
                finished_at = normalize_shanghai_datetime(datetime.fromisoformat(finished_at_raw))
            except ValueError:
                finished_at = shanghai_now()
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=next_sequence,
            node_key=str(entry.get("node_key") or "graph_node"),
            step_kind="graph_node_completed",
            status=str(entry.get("status") or "completed"),
            narrative=str(entry.get("narrative") or "图节点已完成执行。"),
            input_payload=dict(entry.get("input_payload") or {}),
            output_payload=dict(entry.get("output_payload") or {}),
            error_payload=dict(entry.get("error_payload") or {}),
            finished_at=finished_at or shanghai_now(),
        )
        next_sequence += 1


def _workflow_snapshot_payload(workflow_config: AgentWorkflowRead) -> dict[str, Any]:
    return workflow_config.model_dump(mode="json")


def _run_workflow_snapshot(run: AgentRun, fallback: AgentWorkflowRead) -> dict[str, Any]:
    snapshot = dict(run.workflow_snapshot or {})
    if snapshot:
        return protect_sensitive_data(snapshot, purpose=RUNTIME_STATE_SECRET_PURPOSE)
    snapshot = dict(run.input_payload.get("workflow_config_snapshot") or {})
    if snapshot:
        return protect_sensitive_data(snapshot, purpose=RUNTIME_STATE_SECRET_PURPOSE)
    return protect_sensitive_data(
        fallback.model_dump(mode="json"),
        purpose=RUNTIME_STATE_SECRET_PURPOSE,
    )


def _workflow_requires_ai(workflow_snapshot: dict[str, Any]) -> bool:
    return any(
        str(item.get("type") or "") in {"ai.task", "ai_task"}
        for item in list(dict(workflow_snapshot.get("graph") or {}).get("nodes") or [])
        if isinstance(item, dict)
    )


def _pending_wait_payload(run: AgentRun) -> dict[str, Any]:
    return dict(run.input_payload.get("pending_wait") or {})


def _wait_available_at(wait_payload: dict[str, Any]) -> datetime | None:
    wait_type = str(wait_payload.get("wait_type") or "").strip()
    timestamp_field = "timeout_at" if wait_type == "event" else "resume_at"
    timestamp_raw = str(wait_payload.get(timestamp_field) or "").strip()
    if timestamp_raw:
        try:
            return normalize_shanghai_datetime(datetime.fromisoformat(timestamp_raw))
        except ValueError:
            return shanghai_now()
    if wait_type in {"event", "gate"}:
        return None
    return shanghai_now()


def _next_resume_value(run: AgentRun, *, now: datetime) -> dict[str, Any] | None:
    input_payload = dict(run.input_payload or {})
    pending_wait = _pending_wait_payload(run)
    queued_resume = input_payload.get("resume_value")
    if isinstance(queued_resume, dict):
        return dict(queued_resume)
    if not pending_wait:
        return None
    wait_type = str(pending_wait.get("wait_type") or "").strip()
    if wait_type in {"delay", "poll"}:
        resume_at_raw = str(pending_wait.get("resume_at") or "").strip()
        if resume_at_raw:
            try:
                resume_at = normalize_shanghai_datetime(datetime.fromisoformat(resume_at_raw))
            except ValueError:
                resume_at = now
            if resume_at > now:
                return None
        return {"resumed_at": now.isoformat(), "attempt": pending_wait.get("attempt")}
    if wait_type == "event":
        timeout_at_raw = str(pending_wait.get("timeout_at") or "").strip()
        if timeout_at_raw:
            try:
                timeout_at = normalize_shanghai_datetime(datetime.fromisoformat(timeout_at_raw))
            except ValueError:
                timeout_at = now
            if timeout_at <= now:
                return {"timeout": True, "resumed_at": now.isoformat()}
        return None
    if wait_type == "gate":
        return None
    return {"resumed_at": now.isoformat()}


def _run_state_payload(run: AgentRun, workflow_snapshot: dict[str, Any]) -> dict[str, Any]:
    input_payload = dict(run.input_payload or {})
    return protect_sensitive_data(
        {
            "run_id": run.id,
            "workflow_key": run.workflow_key,
            "execution_mode": run.execution_mode,
            "requested_by": {
                "type": run.requested_by_type,
                "id": run.requested_by_id,
            },
            "authorization_scopes": list(run.authorization_scopes or []),
            "trigger_kind": run.trigger_kind,
            "trigger_event": run.trigger_event,
            "target_type": run.target_type,
            "target_id": run.target_id,
            "inputs": dict(input_payload),
            "context_payload": dict(run.context_payload or {}),
            "workflow_config": workflow_snapshot,
        },
        purpose=RUNTIME_STATE_SECRET_PURPOSE,
    )


def _finalize_interrupt(
    session: Session,
    *,
    run: AgentRun,
    first_interrupt: Any,
    interrupt_payload: dict[str, Any],
) -> None:
    interrupt_node_key = str(interrupt_payload.get("node_id") or "workflow_interrupt")
    kind = str(interrupt_payload.get("kind") or "approval")
    if kind == "approval":
        transition_agent_run(run, "awaiting_approval")
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=_next_run_sequence_no(session, run.id),
            node_key=interrupt_node_key,
            step_kind="interrupt_requested",
            status="interrupted",
            narrative="工作流请求人工审批。",
            output_payload={"request": interrupt_payload},
            finished_at=shanghai_now(),
        )
        interrupt_id = getattr(first_interrupt, "id", None) or f"{run.id}:approval"
        repo.create_agent_run_approval(
            session,
            run_id=run.id,
            step_id=None,
            interrupt_id=interrupt_id,
            node_key=interrupt_node_key,
            approval_type=str(interrupt_payload.get("approval_type") or "manual_review"),
            request_payload={"value": interrupt_payload},
        )
        return

    if kind == "wait":
        input_payload = dict(run.input_payload or {})
        input_payload["pending_wait"] = protect_sensitive_data(
            interrupt_payload,
            purpose=RUNTIME_STATE_SECRET_PURPOSE,
        )
        input_payload.pop("resume_value", None)
        run.input_payload = input_payload
        transition_agent_run(run, "queued")
        run.available_at = _wait_available_at(interrupt_payload)
        run.attempt_count = 0
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=_next_run_sequence_no(session, run.id),
            node_key=interrupt_node_key,
            step_kind="interrupt_requested",
            status="interrupted",
            narrative="工作流进入等待状态。",
            output_payload={"request": interrupt_payload},
            finished_at=shanghai_now(),
        )
        return

    raise ValidationError(f"Unsupported workflow interrupt kind: {kind}")


def _complete_run_from_result(session: Session, *, run: AgentRun, result: dict[str, Any]) -> None:
    transition_agent_run(run, "completed")
    run.error_code = None
    run.error_message = None
    run.result_payload = _extract_result_payload(result)
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=_next_run_sequence_no(session, run.id),
        node_key="workflow_complete",
        step_kind="node_completed",
        status="completed",
        narrative="工作流已完成。",
        output_payload=run.result_payload,
        finished_at=shanghai_now(),
    )


def reduce_runtime_result(
    session: Session,
    runtime: AutomationRuntime,
    *,
    run: AgentRun,
    result: dict[str, Any],
    workflow_snapshot: dict[str, Any],
) -> None:
    """Persist one invoke/resume result, including repeated interrupts."""

    snapshot = runtime.get_state(
        thread_id=run.thread_id,
        workflow_config=workflow_snapshot,
    )
    run.latest_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
    run.checkpoint_ns = snapshot.config.get("configurable", {}).get("checkpoint_ns")
    _persist_graph_trace_steps(session, run, _extract_execution_trace(result, snapshot))
    interrupts = result.get("__interrupt__") or []
    if interrupts:
        first = interrupts[0]
        interrupt_value = getattr(first, "value", None) if first is not None else None
        interrupt_payload = dict(interrupt_value or {}) if isinstance(interrupt_value, dict) else {}
        _finalize_interrupt(
            session,
            run=run,
            first_interrupt=first,
            interrupt_payload=interrupt_payload,
        )
        return
    _complete_run_from_result(session, run=run, result=result)


def _execute_one_run(
    session: Session,
    runtime: AutomationRuntime,
    run: AgentRun,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_RUN_LEASE_SECONDS,
) -> bool:
    if run.status != "running" or run.lease_owner != worker_id:
        return False
    run_id = run.id
    thread_id = run.thread_id

    now = shanghai_now()
    resume_value = reveal_sensitive_data(
        _next_resume_value(run, now=now),
        purpose=RUNTIME_STATE_SECRET_PURPOSE,
    )
    pending_wait = _pending_wait_payload(run)
    if pending_wait and resume_value is None:
        transition_agent_run(run, "queued", at=now)
        run.available_at = _wait_available_at(pending_wait)
        run.attempt_count = 0
        session.commit()
        return False

    if not repo.list_agent_run_steps(session, run_id=run.id):
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=1,
            node_key="workflow_dispatch",
            step_kind="node_entered",
            status="running",
            narrative=f"开始执行工作流 {run.workflow_key}。",
            input_payload=run.input_payload,
            started_at=now,
        )

    workflow_config = find_agent_workflow(session, run.workflow_key) or fallback_workflow_config(run)
    workflow_snapshot = _run_workflow_snapshot(run, workflow_config)
    if not run.workflow_snapshot:
        run.workflow_snapshot = deepcopy(workflow_snapshot)
        run.workflow_fingerprint = _workflow_fingerprint(workflow_snapshot)
    input_payload = dict(run.input_payload or {})
    input_payload.setdefault("workflow_config_snapshot", workflow_snapshot)
    if resume_value is not None:
        input_payload["resume_value"] = resume_value
    run.input_payload = input_payload
    if not repo.heartbeat_agent_run(
        session,
        run_id=run.id,
        worker_id=worker_id,
        now=now,
        lease_seconds=lease_seconds,
    ):
        session.rollback()
        return False
    session.commit()

    if cancel_run_at_node_boundary(session, run=run):
        session.commit()
        return True

    model_config = get_agent_model_config_resolved(session)
    runtime_model_config = agent_model_runtime_config(model_config)
    known_model_secrets = (
        model_config.openai_compatible.api_key,
        model_config.openai_compatible.base_url,
    )
    if _workflow_requires_ai(workflow_snapshot):
        model_sources = (model_config.chatgpt_oauth, model_config.openai_compatible)
        if not any(source.enabled for source in model_sources):
            _mark_run_cancelled(
                session,
                run=run,
                sequence_no=_next_run_sequence_no(session, run.id),
                narrative="Agent 模型开关已关闭，当前工作流不执行。",
                reason="model_disabled",
            )
            session.commit()
            return True
        if not any(source.enabled and source.is_ready for source in model_sources):
            _mark_run_failed(
                session,
                run=run,
                sequence_no=_next_run_sequence_no(session, run.id),
                narrative="Agent 模型配置不完整，无法执行工作流。",
                error_code="ModelConfigNotReady",
                error_message="Agent model config is not ready",
            )
            session.commit()
            return True
    session.commit()
    node_boundary_hook = _make_node_boundary_hook(
        run_id=run_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    try:
        if resume_value is not None and run.latest_checkpoint_id:
            result = runtime.resume(
                thread_id=thread_id,
                resume_value=resume_value,
                workflow_config=workflow_snapshot,
                node_boundary_hook=node_boundary_hook,
                model_config=runtime_model_config,
            )
            input_payload = dict(run.input_payload or {})
            input_payload.pop("pending_wait", None)
            input_payload.pop("resume_value", None)
            run.input_payload = input_payload
        else:
            result = runtime.invoke(
                _run_state_payload(run, workflow_snapshot),
                thread_id=thread_id,
                node_boundary_hook=node_boundary_hook,
                model_config=runtime_model_config,
            )
        if not repo.heartbeat_agent_run(
            session,
            run_id=run.id,
            worker_id=worker_id,
            now=shanghai_now(),
            lease_seconds=lease_seconds,
        ):
            session.rollback()
            return False
        session.commit()
        run = repo.get_agent_run(session, run_id) or run
        if cancel_run_at_node_boundary(session, run=run):
            session.commit()
            return True
        reduce_runtime_result(
            session,
            runtime,
            run=run,
            result=result,
            workflow_snapshot=workflow_snapshot,
        )
        session.commit()
        return True
    except AgentRunCancellationRequested as exc:
        logger.info(
            "Agent run cancellation observed at node boundary",
            extra={"run_id": run_id, "node_id": exc.node_id},
        )
        _safe_rollback_runtime_session(session, run_id=run_id)
        return _persist_runtime_cancellation(run_id=run_id, worker_id=worker_id)
    except AgentRunLeaseLost as exc:
        logger.warning(
            "Agent run lease lost at node boundary",
            extra={"run_id": run_id, "node_id": exc.node_id, "worker_id": worker_id},
        )
        _safe_rollback_runtime_session(session, run_id=run_id)
        return False
    except Exception as exc:
        safe_error_message = safe_exception_detail(exc, known_secrets=known_model_secrets)
        logger.error(
            "Agent run execution failed",
            extra={"run_id": run_id, "worker_id": worker_id, "error_code": exc.__class__.__name__},
        )
        _safe_rollback_runtime_session(session, run_id=run_id)
        return _persist_runtime_failure(
            run_id=run_id,
            worker_id=worker_id,
            error_code=exc.__class__.__name__,
            error_message=safe_error_message,
            retryable=_is_retryable_runtime_error(exc),
        )


def _schedule_slot(config: dict[str, Any], *, now: datetime) -> tuple[bool, str]:
    interval_seconds = int(config.get("interval_seconds") or 0)
    if interval_seconds > 0:
        slot_start = int(now.timestamp()) // interval_seconds * interval_seconds
        return True, f"interval:{slot_start}"
    cron = str(config.get("cron") or "").strip()
    if cron:
        trigger = CronTrigger.from_crontab(cron, timezone=str(now.tzinfo or BEIJING_TZ))
        previous_window = now - timedelta(minutes=1)
        next_fire = trigger.get_next_fire_time(None, previous_window)
        if next_fire is not None and next_fire <= now:
            return True, f"cron:{next_fire.replace(second=0, microsecond=0).isoformat()}"
    return False, ""


def dispatch_due_schedule_runs(session: Session, *, now: datetime | None = None) -> int:
    current = normalize_shanghai_datetime(now) if now is not None else shanghai_now()
    existing_slots = {
        (
            item.workflow_key,
            str((item.input_payload or {}).get("trigger_binding_id") or ""),
            str((item.input_payload or {}).get("schedule_slot") or ""),
        )
        for item in repo.list_agent_runs(session, limit=200)
        if item.status in {"queued", "running", "awaiting_approval"}
    }
    created = 0
    for workflow, binding in list_workflow_bindings_by_type(session, binding_type="trigger.schedule"):
        config = dict(binding.config or {})
        due, slot = _schedule_slot(config, now=current)
        if not due:
            continue
        dedupe_key = (workflow.key, binding.id, slot)
        if dedupe_key in existing_slots:
            continue
        idempotency_key = f"schedule:{binding.id}:{slot}"
        if (
            repo.get_agent_run_by_idempotency_key(
                session,
                workflow_key=workflow.key,
                idempotency_key=idempotency_key,
            )
            is not None
        ):
            existing_slots.add(dedupe_key)
            continue
        enqueue_workflow_run(
            session,
            workflow_key=workflow.key,
            trigger_kind="schedule",
            trigger_event=str(config.get("event_type") or f"schedule:{binding.id}"),
            target_type=str(config.get("target_type") or "").strip() or None,
            target_id=None,
            input_payload={"trigger_binding_id": binding.id, "schedule_slot": slot},
            context_payload={"scheduled_at": current.isoformat(), "binding_id": binding.id},
            idempotency_key=idempotency_key,
            principal=full_access_run_principal(
                "schedule",
                f"{workflow.key}:{binding.id}",
            ),
            autocommit=False,
        )
        existing_slots.add(dedupe_key)
        created += 1
    if created:
        session.commit()
    return created


def execute_due_runs(
    session: Session,
    runtime: AutomationRuntime,
    *,
    worker_id: str | None = None,
    lease_seconds: int = DEFAULT_RUN_LEASE_SECONDS,
    recover_expired: bool = True,
) -> int:
    current_worker_id = worker_id or _PROCESS_WORKER_ID
    if recover_expired:
        repo.recover_expired_agent_runs(session, now=shanghai_now())
        session.commit()
    dispatch_due_schedule_runs(session)
    now = shanghai_now()
    candidate_ids = [item.id for item in repo.list_claimable_agent_runs(session, now=now, limit=50)]
    processed = 0
    for run_id in candidate_ids:
        run = repo.claim_agent_run(
            session,
            run_id=run_id,
            worker_id=current_worker_id,
            now=shanghai_now(),
            lease_seconds=lease_seconds,
        )
        session.commit()
        if run is not None and _execute_one_run(
            session,
            runtime,
            run,
            worker_id=current_worker_id,
            lease_seconds=lease_seconds,
        ):
            processed += 1
    return processed


def execute_run_now(
    session: Session,
    runtime: AutomationRuntime,
    *,
    run_id: str,
    worker_id: str | None = None,
    lease_seconds: int = DEFAULT_RUN_LEASE_SECONDS,
) -> bool:
    """Atomically claim and execute one explicitly requested run."""

    current_worker_id = worker_id or _PROCESS_WORKER_ID
    run = repo.claim_agent_run(
        session,
        run_id=run_id,
        worker_id=current_worker_id,
        now=shanghai_now(),
        lease_seconds=lease_seconds,
    )
    session.commit()
    if run is None:
        return False
    return _execute_one_run(
        session,
        runtime,
        run,
        worker_id=current_worker_id,
        lease_seconds=lease_seconds,
    )


def emit_event(session: Session, event: AutomationEvent) -> None:
    subscriptions = repo.list_active_webhook_subscriptions(session, event_type=event.event_type)
    for subscription in subscriptions:
        if subscription.event_types and event.event_type not in subscription.event_types:
            continue
        repo.create_webhook_delivery(session, subscription=subscription, event=event)

    for run in repo.list_agent_runs(session, limit=200):
        if run.status != "queued":
            continue
        pending_wait = _pending_wait_payload(run)
        if str(pending_wait.get("wait_type") or "") != "event":
            continue
        expected_event = str(pending_wait.get("event_type") or "").strip()
        expected_target = str(pending_wait.get("target_type") or "").strip()
        if expected_event and expected_event != event.event_type:
            continue
        if expected_target and expected_target != event.target_type:
            continue
        input_payload = dict(run.input_payload or {})
        input_payload["resume_value"] = protect_sensitive_data(
            {"event": event.model_dump()},
            purpose=RUNTIME_STATE_SECRET_PURPOSE,
        )
        run.input_payload = input_payload
        run.available_at = shanghai_now()

    from aerisun.domain.automation.settings import list_workflows_for_event

    workflows = list_workflows_for_event(
        session,
        event_type=event.event_type,
        target_type=event.target_type,
    )
    for workflow in workflows:
        enqueue_workflow_run(
            session,
            workflow_key=workflow.key,
            trigger_kind="event",
            trigger_event=event.event_type,
            target_type=event.target_type,
            target_id=event.target_id,
            input_payload={"event_id": event.event_id},
            context_payload=event.payload,
            idempotency_key=f"event:{event.event_id}",
            principal=full_access_run_principal("domain_event", event.event_id),
            autocommit=False,
        )
    session.commit()
