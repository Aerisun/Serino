from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from aerisun.core.db import get_session_factory
from aerisun.domain.agent.capabilities.registry import execute_capability
from aerisun.domain.exceptions import ValidationError


class ModerationWorkflowState(TypedDict, total=False):
    run_id: str
    workflow_key: str
    workflow_template: str
    target_type: str
    target_id: str
    trigger_event: str
    context_payload: dict[str, Any]
    workflow_config: dict[str, Any]
    model_config: dict[str, Any]
    evaluation: dict[str, Any]
    approval_decision: dict[str, Any]
    result_payload: dict[str, Any]


class AutomationRuntime:
    def __init__(self, *, checkpoint_path: Path) -> None:
        self._checkpoint_path = checkpoint_path
        self._connection: sqlite3.Connection | None = None
        self._checkpointer: SqliteSaver | None = None
        self._graph = None

    def start(self) -> None:
        if self._graph is not None:
            return
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._checkpoint_path), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._connection)
        self._graph = _build_moderation_graph(self._checkpointer)

    def stop(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._checkpointer = None
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            raise RuntimeError("Automation runtime not started")
        return self._graph

    def invoke(self, state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        return self.graph.invoke(state, config={"configurable": {"thread_id": thread_id}})

    def resume(self, *, thread_id: str, resume_value: Any) -> dict[str, Any]:
        return self.graph.invoke(Command(resume=resume_value), config={"configurable": {"thread_id": thread_id}})

    def get_state(self, *, thread_id: str, checkpoint_id: str | None = None):
        config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        return self.graph.get_state(config)

    def get_state_history(self, *, thread_id: str):
        return list(self.graph.get_state_history({"configurable": {"thread_id": thread_id}}))


def _load_target_context(state: ModerationWorkflowState) -> ModerationWorkflowState:
    payload = dict(state.get("context_payload") or {})
    payload.setdefault("loaded_at", datetime.now(UTC).isoformat())
    return {"context_payload": payload}


def _fallback_evaluation(
    state: ModerationWorkflowState,
    *,
    reason: str,
) -> dict[str, Any]:
    context_payload = dict(state.get("context_payload") or {})
    workflow_config = dict(state.get("workflow_config") or {})
    preview = context_payload.get("body_preview") or ""
    needs_approval = bool(workflow_config.get("require_human_approval", True)) or reason.startswith("model_error")
    target_type = state.get("target_type") or "target"
    target_id = state.get("target_id") or "-"
    return {
        "summary": f"需要确认 {target_type}:{target_id} 的处理动作。",
        "body_preview": preview,
        "needs_approval": needs_approval,
        "proposed_action": "approve",
        "source": "fallback",
        "reason": reason,
    }


def _build_messages(state: ModerationWorkflowState) -> list[dict[str, str]]:
    model_config = dict(state.get("model_config") or {})
    workflow_config = dict(state.get("workflow_config") or {})
    context_payload = dict(state.get("context_payload") or {})
    system_prompt = (
        str(model_config.get("advisory_prompt") or "").strip()
        or "Return strict JSON with keys summary, needs_approval, and proposed_action."
    )
    if workflow_config.get("instructions"):
        system_prompt = f"{system_prompt}\n\nWorkflow instructions:\n{workflow_config['instructions']}"
    user_payload = {
        "workflow_key": state.get("workflow_key"),
        "trigger_event": state.get("trigger_event"),
        "target_type": state.get("target_type"),
        "target_id": state.get("target_id"),
        "require_human_approval": bool(workflow_config.get("require_human_approval", True)),
        "context_payload": context_payload,
    }
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Assess this website moderation event. "
                "Respond with strict JSON only.\n"
                f"{json.dumps(user_payload, ensure_ascii=False)}"
            ),
        },
    ]


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _extract_message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Missing model choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValueError("Missing model message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "\n".join(part for part in texts if part)
    raise ValueError("Unsupported model content")


def _parse_json_object(content: str) -> dict[str, Any]:
    candidate = content.strip()
    if candidate.startswith("```"):
        lines = [line for line in candidate.splitlines() if not line.strip().startswith("```")]
        candidate = "\n".join(lines).strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response does not contain a JSON object")
    parsed = json.loads(candidate[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON is not an object")
    return parsed


def _safe_json_payload(response: httpx.Response, *, endpoint: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        content_type = str(response.headers.get("content-type") or "").lower()
        body_preview = response.text.strip()
        lower_preview = body_preview.lower()
        if (
            "text/html" in content_type
            or lower_preview.startswith("<!doctype html")
            or lower_preview.startswith("<html")
        ):
            raise ValidationError(
                f"Model endpoint returned HTML instead of JSON at {endpoint}. "
                "Please verify base_url points to an OpenAI-compatible API endpoint "
                "(for example: https://api.openai.com/v1)."
            ) from exc
        if body_preview:
            raise ValidationError(
                f"Model endpoint returned non-JSON payload (HTTP {response.status_code}) at {endpoint}"
            ) from exc
        raise ValidationError(
            f"Model endpoint returned an empty response body (HTTP {response.status_code}) at {endpoint}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"Model endpoint JSON payload must be an object at {endpoint}")
    return payload


def _invoke_model_json(model_config: dict[str, Any], *, messages: list[dict[str, str]]) -> dict[str, Any]:
    provider = str(model_config.get("provider") or "openai_compatible").strip() or "openai_compatible"
    base_url = str(model_config.get("base_url") or "").strip()
    model_name = str(model_config.get("model") or "").strip()
    api_key = str(model_config.get("api_key") or "").strip()
    if provider != "openai_compatible":
        raise ValidationError(f"Unsupported model provider: {provider}")
    if not (base_url and model_name and api_key):
        raise ValidationError("Model config is incomplete")

    endpoint = _chat_completions_url(base_url)
    timeout_seconds = float(model_config.get("timeout_seconds") or 20)
    try:
        response = httpx.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": model_name,
                "temperature": float(model_config.get("temperature") or 0.2),
                "messages": messages,
                "response_format": {"type": "json_object"},
            },
            timeout=httpx.Timeout(connect=min(timeout_seconds, 20.0), read=timeout_seconds, write=30.0, pool=20.0),
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ValidationError(
            f"Model endpoint request timed out after {int(timeout_seconds)}s (effective timeout): {endpoint}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        body_preview = exc.response.text.strip()[:200] if exc.response is not None else ""
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        detail = f": {body_preview}" if body_preview else ""
        raise ValidationError(f"Model endpoint returned HTTP {status_code} at {endpoint}{detail}") from exc
    except httpx.HTTPError as exc:
        raise ValidationError(f"Model endpoint request failed at {endpoint}: {exc}") from exc

    payload = _safe_json_payload(response, endpoint=endpoint)
    try:
        content = _extract_message_content(payload)
    except ValueError as exc:
        raise ValidationError(f"Model endpoint payload format is invalid: {exc}") from exc

    try:
        return _parse_json_object(content)
    except ValueError as exc:
        preview = content.strip().replace("\n", " ")[:200]
        extra = f" Raw content: {preview}" if preview else ""
        raise ValidationError(f"Model content is not a valid JSON object.{extra}") from exc


def invoke_model_json(model_config: dict[str, Any], *, messages: list[dict[str, str]]) -> dict[str, Any]:
    return _invoke_model_json(model_config, messages=messages)


def probe_model_config(model_config: dict[str, Any]) -> dict[str, str]:
    parsed = _invoke_model_json(
        model_config,
        messages=[
            {
                "role": "system",
                "content": "Return strict JSON with keys summary, needs_approval, and proposed_action.",
            },
            {
                "role": "user",
                "content": (
                    "This is a connectivity test. Return JSON with summary='connection_ok', "
                    "needs_approval=false, proposed_action='approve'."
                ),
            },
        ],
    )
    return {
        "model": str(model_config.get("model") or ""),
        "endpoint": _chat_completions_url(str(model_config.get("base_url") or "")),
        "summary": str(parsed.get("summary") or "connection_ok"),
    }


def _evaluate_moderation(state: ModerationWorkflowState) -> ModerationWorkflowState:
    context_payload = dict(state.get("context_payload") or {})
    workflow_config = dict(state.get("workflow_config") or {})
    model_config = dict(state.get("model_config") or {})
    preview = context_payload.get("body_preview") or ""
    if not (
        str(model_config.get("base_url") or "").strip()
        and str(model_config.get("model") or "").strip()
        and str(model_config.get("api_key") or "").strip()
    ):
        return {"evaluation": _fallback_evaluation(state, reason="model_config_incomplete")}

    try:
        parsed = _invoke_model_json(model_config, messages=_build_messages(state))
        needs_approval = bool(parsed.get("needs_approval"))
        if bool(workflow_config.get("require_human_approval", True)):
            needs_approval = True
        return {
            "evaluation": {
                "summary": str(parsed.get("summary") or f"已完成 {state.get('workflow_key') or 'workflow'} 分析。"),
                "body_preview": preview,
                "needs_approval": needs_approval,
                "proposed_action": str(parsed.get("proposed_action") or "approve"),
                "source": "llm",
                "reason": "model_response",
            }
        }
    except Exception as exc:
        return {"evaluation": _fallback_evaluation(state, reason=f"model_error:{exc.__class__.__name__}")}


def _request_approval(state: ModerationWorkflowState) -> ModerationWorkflowState:
    evaluation = dict(state.get("evaluation") or {})
    response = interrupt(
        {
            "approval_type": "moderation_decision",
            "run_id": state.get("run_id"),
            "target_type": state.get("target_type"),
            "target_id": state.get("target_id"),
            "message": evaluation.get("summary") or "需要人工审批。",
            "proposed_action": evaluation.get("proposed_action") or "approve",
            "body_preview": evaluation.get("body_preview") or "",
        }
    )
    return {"approval_decision": response}


def _route_after_evaluation(state: ModerationWorkflowState) -> str:
    evaluation = dict(state.get("evaluation") or {})
    return "request_approval" if evaluation.get("needs_approval", True) else "apply_decision"


def _apply_decision(state: ModerationWorkflowState) -> ModerationWorkflowState:
    evaluation = dict(state.get("evaluation") or {})
    decision = dict(state.get("approval_decision") or {})
    action = decision.get("action") or decision.get("proposed_action") or evaluation.get("proposed_action") or "approve"
    action = str(action).strip().lower() or "approve"
    reason = decision.get("reason") or evaluation.get("summary")
    workflow_template = str(state.get("workflow_template") or "").strip()
    target_id = str(state.get("target_id") or "").strip()

    moderation_templates = {"community_moderation", "comment_moderation", "guestbook_moderation"}
    has_manual_decision = bool(decision.get("action"))
    if workflow_template in moderation_templates and action == "reject" and not has_manual_decision:
        # In auto mode, an AI veto should not hard-reject public content.
        # Keep the item pending so human moderators can review it later.
        return {
            "result_payload": {
                "action": "pending",
                "target_type": state.get("target_type"),
                "target_id": target_id,
                "applied": False,
                "workflow_key": state.get("workflow_key"),
                "workflow_template": workflow_template,
                "evaluation": {
                    "summary": evaluation.get("summary"),
                    "source": evaluation.get("source"),
                    "needs_approval": evaluation.get("needs_approval"),
                },
                "reason": reason,
                "execution": {
                    "capability": "moderation_deferred",
                    "result": {
                        "status": "pending",
                        "deferred": True,
                        "note": "Auto reject is converted to pending for human review.",
                    },
                },
            }
        }

    if workflow_template in {"community_moderation", "comment_moderation"}:
        if not target_id:
            raise ValidationError("Target id is required")
        if state.get("target_type") == "comment":
            with get_session_factory()() as session:
                applied_result = execute_capability(
                    session,
                    kind="tool",
                    name="moderate_comment",
                    comment_id=target_id,
                    action=action,
                    reason=reason,
                )
        elif state.get("target_type") == "guestbook":
            with get_session_factory()() as session:
                applied_result = execute_capability(
                    session,
                    kind="tool",
                    name="moderate_guestbook_entry",
                    entry_id=target_id,
                    action=action,
                    reason=reason,
                )
        else:
            raise ValidationError(f"Unsupported moderation target_type: {state.get('target_type')!r}")
    elif workflow_template == "guestbook_moderation":
        if not target_id:
            raise ValidationError("Guestbook target_id is required")
        with get_session_factory()() as session:
            applied_result = execute_capability(
                session,
                kind="tool",
                name="moderate_guestbook_entry",
                entry_id=target_id,
                action=action,
                reason=reason,
            )
    elif workflow_template == "content_publish_review":
        applied_result = {
            "status": "review_recorded",
            "note": "content_publish_review template is reserved for a future publish executor.",
        }
    else:
        raise ValidationError(f"Unsupported workflow template: {workflow_template or 'unknown'}")

    return {
        "result_payload": {
            "action": action,
            "target_type": state.get("target_type"),
            "target_id": target_id,
            "applied": workflow_template != "content_publish_review",
            "workflow_key": state.get("workflow_key"),
            "workflow_template": workflow_template,
            "evaluation": {
                "summary": evaluation.get("summary"),
                "source": evaluation.get("source"),
                "needs_approval": evaluation.get("needs_approval"),
            },
            "reason": reason,
            "execution": {
                "capability": (
                    "moderate_comment"
                    if state.get("target_type") == "comment"
                    else "moderate_guestbook_entry"
                    if state.get("target_type") == "guestbook"
                    else "content_publish_review"
                ),
                "result": applied_result,
            },
        }
    }


def _build_moderation_graph(checkpointer: SqliteSaver):
    builder = StateGraph(ModerationWorkflowState)
    builder.add_node("load_target_context", _load_target_context)
    builder.add_node("evaluate_moderation", _evaluate_moderation)
    builder.add_node("request_approval", _request_approval)
    builder.add_node("apply_decision", _apply_decision)
    builder.add_edge(START, "load_target_context")
    builder.add_edge("load_target_context", "evaluate_moderation")
    builder.add_conditional_edges("evaluate_moderation", _route_after_evaluation)
    builder.add_edge("request_approval", "apply_decision")
    builder.add_edge("apply_decision", END)
    return builder.compile(checkpointer=checkpointer)
