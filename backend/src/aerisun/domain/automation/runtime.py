from __future__ import annotations

import ast
import hashlib
import json
import logging
import sqlite3
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

import httpx
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_jsonschema
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from aerisun.core.db import get_session_factory
from aerisun.core.time import format_beijing_iso_datetime, shanghai_now
from aerisun.domain.agent.capabilities.registry import get_capability_definition
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation.ai_contract_context import build_ai_contract_context
from aerisun.domain.automation.catalog import derive_ai_output_schema
from aerisun.domain.automation.compat import normalize_node_type
from aerisun.domain.automation.compiler import (
    AI_TASK_MOUNT_PORT_IDS,
    EDGE_KIND_CONTROL,
    EDGE_KIND_DATA,
    EDGE_KIND_TRIGGER,
    edge_kind,
    flow_edges,
    mounted_action_surface_keys,
    mounted_tool_surface_keys,
)
from aerisun.domain.automation.models import AutomationEvent
from aerisun.domain.automation.operations import (
    AutomationOperationDefinition,
    execute_operation,
    get_operation_definition,
    list_operation_definitions,
)
from aerisun.domain.automation.tool_surface import (
    execute_action_surface,
    execute_tool_surface,
    get_action_surface,
    get_action_surface_invocation,
    get_tool_surface,
    list_action_surface_invocations,
    list_action_surfaces,
)
from aerisun.domain.exceptions import StateConflict, ValidationError

logger = logging.getLogger(__name__)

AI_TASK_INPUT_PORT_IDS = ("input_1", "input_2", "input_3")
FINAL_OUTPUT_TOOL_NAME = "submit_final_output"

_JSONSCHEMA_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


class WorkflowExecutionState(TypedDict, total=False):
    run_id: str
    workflow_key: str
    trigger_kind: str
    trigger_event: str
    target_type: str
    target_id: str
    workflow_config: dict[str, Any]
    model_config: dict[str, Any]
    inputs: dict[str, Any]
    context_payload: dict[str, Any]
    node_outputs: dict[str, Any]
    artifacts: dict[str, Any]
    approval_result: dict[str, Any]
    approval_token: dict[str, Any]
    result_payload: dict[str, Any]
    execution_trace: list[dict[str, Any]]


class _NativeToolCallingUnsupportedError(Exception):
    """Raised when an OpenAI-compatible endpoint rejects native tool calling."""


class _ModelToolCall(TypedDict):
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str


class _ModelTurnResult(TypedDict):
    raw_content: str
    parsed_content: dict[str, Any] | None
    tool_calls: list[_ModelToolCall]
    assistant_message: dict[str, Any]


class AutomationRuntime:
    def __init__(self, *, checkpoint_path: Path) -> None:
        self._checkpoint_path = checkpoint_path
        self._connection: sqlite3.Connection | None = None
        self._checkpointer: SqliteSaver | None = None
        self._graph_cache: dict[str, Any] = {}

    def start(self) -> None:
        if self._checkpointer is not None:
            return
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._checkpoint_path), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._connection)

    def stop(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._checkpointer = None
        self._graph_cache = {}

    @property
    def checkpointer(self) -> SqliteSaver:
        if self._checkpointer is None:
            raise StateConflict("Automation runtime not started")
        return self._checkpointer

    def _graph_for_workflow_config(self, workflow_config: dict[str, Any]):
        graph_payload = dict(workflow_config.get("graph") or {})
        cache_key = hashlib.sha256(
            json.dumps(graph_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        compiled = self._graph_cache.get(cache_key)
        if compiled is not None:
            return compiled
        compiled = _build_runtime_graph(self.checkpointer, graph_payload)
        self._graph_cache[cache_key] = compiled
        return compiled

    def invoke(self, state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        workflow_config = dict(state.get("workflow_config") or {})
        graph = self._graph_for_workflow_config(workflow_config)
        return graph.invoke(state, config={"configurable": {"thread_id": thread_id}})

    def resume(self, *, thread_id: str, resume_value: Any, workflow_config: dict[str, Any]) -> dict[str, Any]:
        graph = self._graph_for_workflow_config(workflow_config)
        return graph.invoke(Command(resume=resume_value), config={"configurable": {"thread_id": thread_id}})

    def get_state(self, *, thread_id: str, workflow_config: dict[str, Any], checkpoint_id: str | None = None):
        graph = self._graph_for_workflow_config(workflow_config)
        config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        return graph.get_state(config)

    def get_state_history(self, *, thread_id: str, workflow_config: dict[str, Any]):
        graph = self._graph_for_workflow_config(workflow_config)
        return list(graph.get_state_history({"configurable": {"thread_id": thread_id}}))


def _copy_outputs(state: WorkflowExecutionState) -> dict[str, Any]:
    return dict(state.get("node_outputs") or {})


def _copy_artifacts(state: WorkflowExecutionState) -> dict[str, Any]:
    return dict(state.get("artifacts") or {})


def _copy_trace(state: WorkflowExecutionState) -> list[dict[str, Any]]:
    return list(state.get("execution_trace") or [])


def _set_node_output(state: WorkflowExecutionState, *, node_id: str, value: dict[str, Any]) -> dict[str, Any]:
    outputs = _copy_outputs(state)
    outputs[node_id] = value
    return outputs


def _append_trace(
    state: WorkflowExecutionState,
    *,
    node_id: str,
    status: str,
    narrative: str,
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    error_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    trace = _copy_trace(state)
    trace.append(
        {
            "node_key": node_id,
            "step_kind": "graph_node_completed",
            "status": status,
            "narrative": narrative,
            "input_payload": input_payload or {},
            "output_payload": output_payload or {},
            "error_payload": error_payload or {},
            "finished_at": format_beijing_iso_datetime(shanghai_now()),
        }
    )
    return trace


def _lookup_path(data: Any, path: str) -> Any:
    current = data
    for segment in path.split("."):
        if not segment:
            continue
        if isinstance(current, dict):
            current = current.get(segment)
            continue
        if isinstance(current, list):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return None
            continue
        current = getattr(current, segment, None)
    return current


def _load_target_context(state: WorkflowExecutionState) -> WorkflowExecutionState:
    payload = dict(state.get("context_payload") or {})
    payload.setdefault("loaded_at", format_beijing_iso_datetime(shanghai_now()))
    return {"context_payload": payload}


def _graph_nodes_map(state: WorkflowExecutionState) -> dict[str, dict[str, Any]]:
    graph = dict((state.get("workflow_config") or {}).get("graph") or {})
    return {
        str(item.get("id") or ""): dict(item)
        for item in graph.get("nodes") or []
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }


def _graph_edges_list(state: WorkflowExecutionState) -> list[dict[str, Any]]:
    graph = dict((state.get("workflow_config") or {}).get("graph") or {})
    return [dict(item) for item in graph.get("edges") or [] if isinstance(item, dict)]


def _previous_node_id(state: WorkflowExecutionState) -> str:
    trace = _copy_trace(state)
    if not trace:
        return ""
    return str(trace[-1].get("node_key") or "").strip()


def _incoming_edge_for_node(state: WorkflowExecutionState, *, node_id: str) -> dict[str, Any] | None:
    previous_node_id = _previous_node_id(state)
    if not previous_node_id:
        return None
    nodes_by_id = _graph_nodes_map(state)
    for edge in _graph_edges_list(state):
        if str(edge.get("source") or "").strip() != previous_node_id:
            continue
        if str(edge.get("target") or "").strip() != node_id:
            continue
        return {"edge": edge, "kind": edge_kind(edge, nodes_by_id=nodes_by_id)}
    return None


def _incoming_edges_for_node(state: WorkflowExecutionState, *, node_id: str) -> list[dict[str, Any]]:
    nodes_by_id = _graph_nodes_map(state)
    items: list[dict[str, Any]] = []
    for edge in _graph_edges_list(state):
        if str(edge.get("target") or "").strip() != node_id:
            continue
        items.append({"edge": edge, "kind": edge_kind(edge, nodes_by_id=nodes_by_id)})
    return items


def _state_with_updates(state: WorkflowExecutionState, updates: WorkflowExecutionState) -> WorkflowExecutionState:
    if not updates:
        return state
    merged = dict(state)
    merged.update(updates)
    return merged


def _approval_mount_sources_for_node(state: WorkflowExecutionState, *, node_id: str) -> list[dict[str, Any]]:
    nodes_by_id = _graph_nodes_map(state)
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _incoming_edges_for_node(state, node_id=node_id):
        edge = dict(item.get("edge") or {})
        if item.get("kind") != EDGE_KIND_CONTROL:
            continue
        if str(edge.get("target_handle") or "").strip() not in AI_TASK_MOUNT_PORT_IDS:
            continue
        source_id = str(edge.get("source") or "").strip()
        if not source_id or source_id in seen:
            continue
        source_node = dict(nodes_by_id.get(source_id) or {})
        if normalize_node_type(str(source_node.get("type") or "")) != "approval.review":
            continue
        sources.append({"node_id": source_id, "config": dict(source_node.get("config") or {})})
        seen.add(source_id)
    return sources


def _node_output_payload(state: WorkflowExecutionState, *, node_id: str) -> dict[str, Any]:
    return dict((state.get("node_outputs") or {}).get(node_id) or {})


def _graph_node_payload(state: WorkflowExecutionState, *, node_id: str) -> dict[str, Any]:
    node = dict(_graph_nodes_map(state).get(node_id) or {})
    return {
        "id": node_id,
        "type": str(node.get("type") or ""),
        "label": str(node.get("label") or node_id),
    }


def _compact_multiline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _summarize_result_lines(result: Any) -> list[str]:
    if result is None:
        return []
    if isinstance(result, dict):
        lines: list[str] = []
        preferred_keys = [
            "status",
            "applied",
            "comment_id",
            "entry_id",
            "content_id",
            "item_id",
            "id",
        ]
        for key in preferred_keys:
            if key in result and result[key] is not None:
                lines.append(f"{key}: {result[key]}")
        if lines:
            return lines
        return [_compact_multiline_json(result)]
    if isinstance(result, list):
        if not result:
            return []
        return [_compact_multiline_json(result)]
    return [str(result)]


def _tool_call_summary_line(item: dict[str, Any]) -> str:
    tool_name = str(item.get("name") or "").strip() or "unknown"
    error = str(item.get("error") or "").strip()
    if error:
        detail = str(item.get("message") or error).strip()
        return f"- {tool_name}: 失败 ({detail})"

    result = item.get("result")
    if isinstance(result, dict):
        parts: list[str] = []
        for key in ("status", "applied", "id", "item_id", "content_id", "title"):
            value = result.get(key)
            if value is not None and str(value).strip():
                parts.append(f"{key}={value}")
        if not parts and isinstance(result.get("items"), list):
            parts.append(f"items={len(result['items'])}")
        if not parts and isinstance(result.get("site"), dict):
            site_title = str(dict(result.get("site") or {}).get("title") or "").strip()
            if site_title:
                parts.append(f"site.title={site_title}")
        if not parts:
            keys = [str(key) for key in list(result.keys())[:4] if str(key).strip()]
            if keys:
                parts.append(f"keys={', '.join(keys)}")
        return f"- {tool_name}: {', '.join(parts) if parts else 'success'}"

    if isinstance(result, list):
        return f"- {tool_name}: items={len(result)}"
    if result is None:
        return f"- {tool_name}: success"
    return f"- {tool_name}: {result}"


def _build_webhook_formatted_text(upstream_output: dict[str, Any]) -> str:
    upstream_summary = str(upstream_output.get("summary") or "").strip()
    execution_summary = str(upstream_output.get("execution_summary") or "").strip()
    execution_result = upstream_output.get("execution_result")
    upstream_reason = str(upstream_output.get("reason") or "").strip()
    upstream_action = str(upstream_output.get("action") or "").strip()
    tool_call_results = [
        dict(item) for item in upstream_output.get("__tool_call_results__") or [] if isinstance(item, dict)
    ]
    node_info = dict(upstream_output.get("node") or {})
    node_label = str(node_info.get("label") or "").strip()
    node_description = str(node_info.get("description") or "").strip()

    lines: list[str] = []
    if node_label:
        lines.append(f"节点：{node_label}")
    if node_description:
        lines.append(f"说明：{node_description}")
    if upstream_summary:
        lines.append(f"摘要：{upstream_summary}")
    if execution_summary:
        lines.append(f"执行：{execution_summary}")
    if upstream_action:
        lines.append(f"动作：{upstream_action}")
    if upstream_reason:
        lines.append(f"原因：{upstream_reason}")

    result_lines = _summarize_result_lines(execution_result)
    if result_lines:
        if lines:
            lines.append("")
        lines.append("执行结果：")
        lines.extend(result_lines)

    if tool_call_results:
        if lines:
            lines.append("")
        lines.append("调用记录：")
        lines.extend(_tool_call_summary_line(item) for item in tool_call_results)

    return "\n".join(lines).strip()


def _ensure_mounted_approval_tokens(state: WorkflowExecutionState, *, node_id: str) -> WorkflowExecutionState:
    approval_mounts = _approval_mount_sources_for_node(state, node_id=node_id)
    if not approval_mounts:
        return {}

    working_state: WorkflowExecutionState = state
    last_updates: WorkflowExecutionState = {}
    for mount in approval_mounts:
        approval_node_id = str(mount.get("node_id") or "").strip()
        if not approval_node_id:
            continue

        existing_payload = _node_output_payload(working_state, node_id=approval_node_id)
        existing_token = dict(existing_payload.get("token") or {})
        if existing_token.get("granted"):
            sync_updates: WorkflowExecutionState = {
                "approval_token": existing_token,
                "approval_result": dict(existing_payload.get("decision") or {}),
            }
            working_state = _state_with_updates(working_state, sync_updates)
            last_updates = sync_updates
            continue

        updates = _execute_approval_node(
            working_state,
            node_id=approval_node_id,
            node_config=dict(mount.get("config") or {}),
        )
        working_state = _state_with_updates(working_state, updates)
        last_updates = updates

        approval_payload = _node_output_payload(working_state, node_id=approval_node_id)
        token = dict(approval_payload.get("token") or {})
        if not bool(token.get("granted")):
            raise ValidationError(f"Execution blocked: approval denied for node {node_id} (gate: {approval_node_id}).")

    return last_updates


def _public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not str(key).startswith("__")}


def _condition_environment(state: WorkflowExecutionState) -> dict[str, Any]:
    env: dict[str, Any] = {
        "inputs": dict(state.get("inputs") or {}),
        "context_payload": dict(state.get("context_payload") or {}),
        "node_outputs": dict(state.get("node_outputs") or {}),
        "artifacts": dict(state.get("artifacts") or {}),
        "result_payload": dict(state.get("result_payload") or {}),
        "approval": dict(state.get("approval_result") or {}),
        "approval_token": dict(state.get("approval_token") or {}),
        "trigger_event": state.get("trigger_event"),
        "target_type": state.get("target_type"),
        "target_id": state.get("target_id"),
    }
    latest_ai = dict(env["artifacts"].get("latest_ai_output") or {})
    env["ai_output"] = latest_ai
    env["summary"] = latest_ai.get("summary")
    env["needs_approval"] = latest_ai.get("needs_approval")
    env["action"] = latest_ai.get("action")
    env["proposed_action"] = latest_ai.get("action") or latest_ai.get("route")
    return env


def _safe_call(name: str, args: list[Any], env: dict[str, Any]) -> Any:
    if name == "path" and len(args) == 1:
        return _lookup_path(env, str(args[0]))
    if name == "contains" and len(args) == 2:
        haystack, needle = args
        return needle in haystack if haystack is not None else False
    if name == "startswith" and len(args) == 2:
        return str(args[0]).startswith(str(args[1]))
    if name == "endswith" and len(args) == 2:
        return str(args[0]).endswith(str(args[1]))
    if name == "lower" and len(args) == 1:
        return str(args[0]).lower()
    if name == "upper" and len(args) == 1:
        return str(args[0]).upper()
    if name == "len" and len(args) == 1:
        return len(args[0])
    raise ValidationError(f"Unsupported condition helper: {name}")


def _eval_expr(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.List):
        return [_eval_expr(item, env) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_expr(item, env) for item in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _eval_expr(key, env): _eval_expr(value, env) for key, value in zip(node.keys, node.values, strict=False)
        }
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_eval_expr(node.operand, env))
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(bool(_eval_expr(value, env)) for value in node.values)
        if isinstance(node.op, ast.Or):
            return any(bool(_eval_expr(value, env)) for value in node.values)
    if isinstance(node, ast.Compare):
        left = _eval_expr(node.left, env)
        for operator, comparator_node in zip(node.ops, node.comparators, strict=False):
            right = _eval_expr(comparator_node, env)
            if isinstance(operator, ast.Eq):
                ok = left == right
            elif isinstance(operator, ast.NotEq):
                ok = left != right
            elif isinstance(operator, ast.Gt):
                ok = left > right
            elif isinstance(operator, ast.GtE):
                ok = left >= right
            elif isinstance(operator, ast.Lt):
                ok = left < right
            elif isinstance(operator, ast.LtE):
                ok = left <= right
            elif isinstance(operator, ast.In):
                ok = left in right if right is not None else False
            elif isinstance(operator, ast.NotIn):
                ok = left not in right if right is not None else True
            else:
                raise ValidationError(f"Unsupported condition operator: {operator.__class__.__name__}")
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        args = [_eval_expr(arg, env) for arg in node.args]
        return _safe_call(node.func.id, args, env)
    if isinstance(node, ast.Subscript):
        value = _eval_expr(node.value, env)
        key = _eval_expr(node.slice, env)
        if isinstance(value, dict):
            return value.get(key)
        return value[key]
    if isinstance(node, ast.Attribute):
        value = _eval_expr(node.value, env)
        if isinstance(value, dict):
            return value.get(node.attr)
        return getattr(value, node.attr, None)
    raise ValidationError(f"Unsupported condition syntax: {node.__class__.__name__}")


def _evaluate_condition_expression(expression: str, state: WorkflowExecutionState) -> Any:
    candidate = expression.strip()
    if not candidate:
        return True
    try:
        tree = ast.parse(candidate, mode="eval")
    except SyntaxError as exc:
        raise ValidationError(f"Invalid condition expression: {candidate}") from exc
    return _eval_expr(tree.body, _condition_environment(state))


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _extract_choice_message(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValidationError("Missing model choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValidationError("Missing model message")
    return message


def _extract_message_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "\n".join(part for part in texts if part)
    if content is None:
        return ""
    raise ValidationError("Unsupported model content")


def _parse_json_object(content: str) -> dict[str, Any]:
    candidate = content.strip()
    if candidate.startswith("```"):
        lines = [line for line in candidate.splitlines() if not line.strip().startswith("```")]
        candidate = "\n".join(lines).strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValidationError("Model response does not contain a JSON object")
    parsed = json.loads(candidate[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValidationError("Model response JSON is not an object")
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


def _parse_tool_call_arguments(raw_arguments: Any) -> tuple[dict[str, Any], str]:
    if isinstance(raw_arguments, dict):
        return dict(raw_arguments), json.dumps(raw_arguments, ensure_ascii=False)
    if raw_arguments is None:
        return {}, "{}"
    if not isinstance(raw_arguments, str):
        raise ValidationError("Model tool call arguments must be a JSON object or JSON string")
    candidate = raw_arguments.strip() or "{}"
    try:
        parsed = json.loads(candidate)
    except ValueError as exc:
        raise ValidationError("Model tool call arguments are not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValidationError("Model tool call arguments JSON is not an object")
    return parsed, candidate


def _extract_native_tool_calls(message: dict[str, Any]) -> list[_ModelToolCall]:
    raw_tool_calls = message.get("tool_calls")
    if raw_tool_calls is None:
        return []
    if not isinstance(raw_tool_calls, list):
        raise ValidationError("Model tool_calls must be a list")
    tool_calls: list[_ModelToolCall] = []
    for index, item in enumerate(raw_tool_calls, start=1):
        if not isinstance(item, dict):
            raise ValidationError("Model tool call must be an object")
        function_payload = item.get("function")
        payload = function_payload if isinstance(function_payload, dict) else item
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValidationError("Model tool call is missing function name")
        arguments, raw_arguments = _parse_tool_call_arguments(payload.get("arguments"))
        tool_call_id = str(item.get("id") or f"call_{index}").strip() or f"call_{index}"
        tool_calls.append(
            {
                "id": tool_call_id,
                "name": name,
                "arguments": arguments,
                "raw_arguments": raw_arguments,
            }
        )
    return tool_calls


def _build_assistant_message_for_history(message: dict[str, Any]) -> dict[str, Any]:
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": _extract_message_content(message),
    }
    native_tool_calls = _extract_native_tool_calls(message)
    if native_tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": item["id"],
                "type": "function",
                "function": {
                    "name": item["name"],
                    "arguments": item["raw_arguments"],
                },
            }
            for item in native_tool_calls
        ]
    return assistant_message


def _native_tool_calling_unsupported(status_code: int, body_preview: str) -> bool:
    if status_code not in {400, 404, 415, 422}:
        return False
    preview = body_preview.lower()
    needles = (
        "unsupported parameter",
        "unknown parameter",
        "tool_choice",
        '"tools"',
        "function calling",
        "does not support tools",
        "does not support function",
    )
    return any(needle in preview for needle in needles)


def _effective_model_timeout_seconds(
    *,
    configured_timeout_seconds: float,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> float:
    effective_timeout = max(float(configured_timeout_seconds or 20), 5.0)
    if not tools:
        return effective_timeout

    effective_timeout = max(effective_timeout, 45.0)
    prompt_size = len(json.dumps(messages, ensure_ascii=False))
    if prompt_size >= 24_000:
        effective_timeout = max(effective_timeout, 75.0)
    elif prompt_size >= 12_000:
        effective_timeout = max(effective_timeout, 60.0)
    return min(effective_timeout, 300.0)


def _is_retryable_http_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504}


def _invoke_model_turn(
    model_config: dict[str, Any],
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    require_json_object: bool = False,
) -> _ModelTurnResult:
    provider = str(model_config.get("provider") or "openai_compatible").strip() or "openai_compatible"
    base_url = str(model_config.get("base_url") or "").strip()
    model_name = str(model_config.get("model") or "").strip()
    api_key = str(model_config.get("api_key") or "").strip()
    if provider != "openai_compatible":
        raise ValidationError(f"Unsupported model provider: {provider}")
    if not (base_url and model_name and api_key):
        raise ValidationError("Model config is incomplete")

    endpoint = _chat_completions_url(base_url)
    configured_timeout_seconds = float(model_config.get("timeout_seconds") or 20)
    timeout_seconds = _effective_model_timeout_seconds(
        configured_timeout_seconds=configured_timeout_seconds,
        messages=messages,
        tools=tools,
    )
    request_payload: dict[str, Any] = {
        "model": model_name,
        "temperature": float(model_config.get("temperature") or 0.2),
        "messages": messages,
    }
    if tools:
        request_payload["tools"] = tools
        request_payload["tool_choice"] = str(tool_choice or "auto")
    elif require_json_object:
        request_payload["response_format"] = {"type": "json_object"}
    max_attempts = 2 if tools else 1
    response: httpx.Response | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=request_payload,
                timeout=httpx.Timeout(connect=min(timeout_seconds, 20.0), read=timeout_seconds, write=30.0, pool=20.0),
            )
            response.raise_for_status()
            break
        except httpx.TimeoutException as exc:
            raise ValidationError(
                "Model endpoint request timed out after "
                f"{int(timeout_seconds)}s (configured {int(configured_timeout_seconds)}s, effective timeout): {endpoint}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            body_preview = exc.response.text.strip()[:200] if exc.response is not None else ""
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            if tools and isinstance(status_code, int) and _native_tool_calling_unsupported(status_code, body_preview):
                raise _NativeToolCallingUnsupportedError(
                    f"Model endpoint does not support native tool calling at {endpoint}"
                ) from exc
            if isinstance(status_code, int) and _is_retryable_http_status(status_code) and attempt < max_attempts:
                continue
            detail = f": {body_preview}" if body_preview else ""
            raise ValidationError(f"Model endpoint returned HTTP {status_code} at {endpoint}{detail}") from exc
        except httpx.TransportError as exc:
            if attempt < max_attempts:
                continue
            raise ValidationError(f"Model endpoint request failed at {endpoint}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ValidationError(f"Model endpoint request failed at {endpoint}: {exc}") from exc

    if response is None:
        raise ValidationError(f"Model endpoint request failed at {endpoint}: empty response")

    payload = _safe_json_payload(response, endpoint=endpoint)
    message = _extract_choice_message(payload)
    content = _extract_message_content(message)
    parsed_content: dict[str, Any] | None = None
    if content.strip():
        try:
            parsed_content = _parse_json_object(content)
        except ValidationError:
            parsed_content = None
    return {
        "raw_content": content,
        "parsed_content": parsed_content,
        "tool_calls": _extract_native_tool_calls(message),
        "assistant_message": _build_assistant_message_for_history(message),
    }


def _invoke_model_json(model_config: dict[str, Any], *, messages: list[dict[str, Any]]) -> dict[str, Any]:
    turn = _invoke_model_turn(model_config, messages=messages, require_json_object=True)
    if turn["parsed_content"] is None:
        preview = turn["raw_content"].strip().replace("\n", " ")[:200]
        extra = f" Raw content: {preview}" if preview else ""
        raise ValidationError(f"Model content is not a valid JSON object.{extra}")
    return turn["parsed_content"]


def invoke_model_json(model_config: dict[str, Any], *, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return _invoke_model_json(model_config, messages=messages)


def probe_model_config(model_config: dict[str, Any]) -> dict[str, str]:
    parsed = _invoke_model_json(
        model_config,
        messages=[
            {
                "role": "system",
                "content": "Return strict JSON with keys summary, ok, and route.",
            },
            {
                "role": "user",
                "content": "This is a connectivity test. Return JSON with summary='connection_ok', ok=true, route='ok'.",
            },
        ],
    )
    return {
        "model": str(model_config.get("model") or ""),
        "endpoint": _chat_completions_url(str(model_config.get("base_url") or "")),
        "summary": str(parsed.get("summary") or "connection_ok"),
    }


def _mapping_source_payload(state: WorkflowExecutionState, source: str) -> Any:
    if source == "inputs":
        return dict(state.get("inputs") or {})
    if source == "context_payload":
        return dict(state.get("context_payload") or {})
    if source == "node_outputs":
        return dict(state.get("node_outputs") or {})
    if source == "artifacts":
        return dict(state.get("artifacts") or {})
    if source == "result_payload":
        return dict(state.get("result_payload") or {})
    if source in {"approval", "approval_result"}:
        return dict(state.get("approval_result") or {})
    if source == "state":
        return state
    if source == "latest_ai":
        return dict(_copy_artifacts(state).get("latest_ai_output") or {})
    return None


def _resolve_argument_mappings(
    state: WorkflowExecutionState,
    mappings: list[dict[str, Any]] | None,
    *,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(defaults or {})
    for item in mappings or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        source = str(item.get("source") or "").strip()
        if not name or not source:
            continue
        if source == "literal":
            payload[name] = item.get("value")
            continue
        if source == "upstream_output":
            upstream_node_id = str(item.get("node_id") or "").strip()
            path = str(item.get("path") or "").strip()
            if not upstream_node_id:
                continue
            node_output = dict(state.get("node_outputs") or {}).get(upstream_node_id)
            resolved = _lookup_path(node_output, path) if path and node_output is not None else node_output
            if resolved is None and name in payload:
                continue
            payload[name] = resolved
            continue
        if source == "expression":
            expression = str(item.get("expression") or "").strip()
            if not expression:
                continue
            try:
                tree = ast.parse(expression, mode="eval")
            except SyntaxError:
                continue
            resolved = _eval_expr(tree.body, _condition_environment(state))
            if resolved is None and name in payload:
                continue
            payload[name] = resolved
            continue
        source_payload = _mapping_source_payload(state, source)
        path = str(item.get("path") or "").strip()
        resolved = _lookup_path(source_payload, path) if path else source_payload
        if resolved is None and name in payload:
            continue
        payload[name] = resolved
    return payload


def _ai_model_config(state: WorkflowExecutionState, node_config: dict[str, Any]) -> dict[str, Any]:
    model_config = dict(state.get("model_config") or {})
    overrides = dict(node_config.get("model_overrides") or {})
    model_config.update({key: value for key, value in overrides.items() if value is not None})
    return model_config


def _resolve_input_contract(
    state: WorkflowExecutionState,
    input_contract: dict[str, Any],
) -> dict[str, Any]:
    """Resolve input contract fields to a flat JSON dict. Agent sees ONLY this."""
    resolved: dict[str, Any] = {}
    for field_def in input_contract.get("fields") or []:
        key = field_def.get("key", "")
        if not key:
            continue
        selector = field_def.get("selector") or {}
        source = selector.get("source", "")

        if source in {"trigger", "webhook"}:
            value = _lookup_path(state.get("context_payload") or {}, selector.get("path", ""))
        elif source == "node_output":
            node_out = (state.get("node_outputs") or {}).get(selector.get("node_id", ""), {})
            value = _lookup_path(node_out, selector.get("path", ""))
        elif source == "artifact":
            value = _lookup_path(state.get("artifacts") or {}, selector.get("path", ""))
        elif source == "literal":
            value = selector.get("value")
        else:
            value = None

        resolved[key] = value
    return resolved


def _ai_shell_input_payload(
    state: WorkflowExecutionState, node_config: dict[str, Any], *, node_id: str
) -> dict[str, Any]:
    graph_nodes = _graph_nodes_map(state)
    incoming_edges = _incoming_edges_for_node(state, node_id=node_id)
    slot_notes = dict(node_config.get("input_slots") or {})
    items: list[dict[str, Any]] = []

    for port_id in AI_TASK_INPUT_PORT_IDS:
        mounted = next(
            (
                item
                for item in incoming_edges
                if item.get("kind") == EDGE_KIND_DATA
                and str(dict(item.get("edge") or {}).get("target_handle") or "") == port_id
            ),
            None,
        )
        if mounted is None:
            continue
        edge = dict(mounted.get("edge") or {})
        source_id = str(edge.get("source") or "").strip()
        source_node = dict(graph_nodes.get(source_id) or {})
        source_type = normalize_node_type(str(source_node.get("type") or ""))
        raw_payload = _node_output_payload(state, node_id=source_id)
        payload = _public_payload(raw_payload)
        slot_note = str(dict(slot_notes.get(port_id) or {}).get("note") or "").strip()

        source_summary = ""
        if source_type == "ai.task":
            source_summary = "Upstream AI structured output."
        elif source_node:
            source_summary = f"Output from {str(source_node.get('label') or source_type or source_id).strip()}."

        items.append(
            {
                "slot": port_id,
                "from_node_id": source_id,
                "from_node_label": str(source_node.get("label") or source_id),
                "from_node_type": source_type,
                "source_summary": source_summary,
                "slot_note": slot_note,
                "data": payload,
            }
        )

    trigger_source = next(
        (
            dict(item.get("edge") or {})
            for item in incoming_edges
            if item.get("kind") == EDGE_KIND_TRIGGER
            and str(dict(item.get("edge") or {}).get("target_handle") or "") in AI_TASK_MOUNT_PORT_IDS
        ),
        None,
    )
    approval_source = next(
        (
            dict(item.get("edge") or {})
            for item in incoming_edges
            if item.get("kind") == EDGE_KIND_CONTROL
            and str(dict(item.get("edge") or {}).get("target_handle") or "") in AI_TASK_MOUNT_PORT_IDS
        ),
        None,
    )
    context_payload = _public_payload(dict(state.get("context_payload") or {}))
    trigger_inputs = _public_payload(dict(state.get("inputs") or {}))

    return {
        "inputs": items,
        "context_payload": context_payload,
        "trigger_inputs": trigger_inputs,
        "mounted_trigger": {
            "node_id": str(trigger_source.get("source") or ""),
            "trigger_event": state.get("trigger_event"),
            "target_type": state.get("target_type"),
            "target_id": state.get("target_id"),
            "context_payload": context_payload,
            "inputs": trigger_inputs,
        }
        if trigger_source
        else None,
        "mounted_approval": _public_payload(
            _node_output_payload(state, node_id=str(approval_source.get("source") or ""))
        )
        if approval_source
        else None,
    }


def _ai_input_payload(state: WorkflowExecutionState, node_config: dict[str, Any], *, node_id: str) -> dict[str, Any]:
    shell_payload = _ai_shell_input_payload(state, node_config, node_id=node_id)
    if shell_payload.get("inputs") or shell_payload.get("mounted_trigger") or shell_payload.get("mounted_approval"):
        return shell_payload
    input_contract = node_config.get("input_contract")
    if isinstance(input_contract, dict):
        return _resolve_input_contract(state, input_contract)
    return {}


def _ai_output_schema(
    node_config: dict[str, Any],
    *,
    node_id: str = "",
    state: WorkflowExecutionState | None = None,
) -> dict[str, Any]:
    output_contract = dict(node_config.get("output_contract") or {})
    explicit_output_schema = (
        output_contract.get("output_schema") or output_contract.get("schema") or output_contract.get("schema_def") or {}
    )
    if explicit_output_schema:
        return dict(explicit_output_schema)

    if state and node_id:
        graph = dict((state.get("workflow_config") or {}).get("graph") or {})
        if graph:
            operation_catalog = list_operation_definitions()
            derived_schema = derive_ai_output_schema(
                node_id=node_id,
                graph=graph,
                operation_catalog=operation_catalog,
                workflow_key=str(state.get("workflow_key") or "").strip() or None,
            )
            if derived_schema.get("properties"):
                return derived_schema

    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
        },
        "required": ["summary"],
    }


def _describe_ai_downstream_contracts(
    state: WorkflowExecutionState,
    *,
    node_id: str,
) -> list[dict[str, Any]]:
    workflow_key = str(state.get("workflow_key") or "").strip()
    graph = dict((state.get("workflow_config") or {}).get("graph") or {})
    graph_nodes = {
        str(item.get("id") or "").strip(): dict(item)
        for item in graph.get("nodes") or []
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    graph_edges = [
        dict(item)
        for item in graph.get("edges") or []
        if isinstance(item, dict) and str(item.get("source") or "").strip() == node_id
    ]
    contracts: list[dict[str, Any]] = []

    for edge in graph_edges:
        if str(edge.get("source_handle") or "").strip() == "route":
            continue
        target_id = str(edge.get("target") or "").strip()
        target_node = graph_nodes.get(target_id)
        if not target_node:
            continue
        target_type = normalize_node_type(str(target_node.get("type") or ""))
        target_label = str(target_node.get("label") or target_id)
        target_config = dict(target_node.get("config") or {})
        contract: dict[str, Any] = {
            "target_node_id": target_id,
            "target_node_type": target_type,
            "target_node_label": target_label,
            "required_fields": [],
            "usage_note": "",
        }

        if target_type.startswith("operation."):
            op_key = str(target_config.get("operation_key") or "").strip()
            op_def = next((item for item in list_operation_definitions() if item.key == op_key), None)
            if op_def is not None:
                props = dict((op_def.input_schema or {}).get("properties") or {})
                contract["required_fields"] = list(props.keys())
            contract["usage_note"] = (
                f"Downstream operation {target_label} will execute with fields from this AI output."
            )
        elif target_type == "apply.action":
            surface_key = str(target_config.get("surface_key") or "").strip()
            surface = next(
                (item for item in list_action_surfaces(workflow_key) if item.key == surface_key),
                None,
            )
            if surface is not None:
                props = dict((surface.input_schema or {}).get("properties") or {})
                contract["required_fields"] = list(props.keys())
                contract["usage_note"] = (
                    f"Action surface {surface.label or surface.key} will consume this AI output and execute the platform action."
                )
            else:
                contract["usage_note"] = f"Downstream action node {target_label} will consume this AI output."
        elif target_type == "notification.webhook":
            contract["usage_note"] = (
                f"Webhook node {target_label} will use this AI output as notification payload/template context."
            )
        elif target_type == "approval.review":
            contract["required_fields"] = ["summary", "needs_approval"]
            contract["usage_note"] = f"Approval node {target_label} will use this AI output as review content."
        elif target_type == "flow.condition":
            contract["usage_note"] = f"Condition node {target_label} will branch based on fields from this AI output."
        elif target_type == "ai.task":
            contract["usage_note"] = (
                f"The next AI node {target_label} will receive this result as structured upstream context."
            )
        else:
            contract["usage_note"] = f"Downstream node {target_label} will consume this AI output."

        contracts.append(contract)

    return contracts


def _build_ai_messages(
    state: WorkflowExecutionState,
    *,
    instructions: str,
    output_schema: dict[str, Any],
    node_id: str,
    contract_context: dict[str, Any] | None = None,
    system_prompt_override: str = "",
    user_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    model_config = dict(state.get("model_config") or {})
    system_prompt = str(model_config.get("advisory_prompt") or "").strip() or "Return strict JSON only."
    if system_prompt_override.strip():
        system_prompt = f"{system_prompt}\n\nNode system prompt:\n{system_prompt_override.strip()}"
    if instructions:
        system_prompt = f"{system_prompt}\n\nNode instructions:\n{instructions}"
    system_prompt = f"{system_prompt}\n\nOutput JSON Schema:\n{json.dumps(output_schema, ensure_ascii=False)}"
    if contract_context:
        system_prompt = (
            f"{system_prompt}\n\nAI contract context:\n"
            f"{json.dumps(contract_context, ensure_ascii=False, indent=2)}"
            "\n\nInterpret this AI contract context carefully:"
            "\n- upstream_inputs explains what has been provided to you and how each input should be understood."
            "\n- downstream_consumers explains what is connected after you, what those nodes can do, and which fields they need."
            "\n- mounted_tools are the only readonly tools available to you in this node. Do not assume any others exist."
            "\n- tool_usage_policy tells you whether tool calls are optional, recommended, or required."
            "\nYou must satisfy both the output JSON schema and the downstream consumer requirements."
        )
    effective_payload = user_payload or {
        "workflow_key": state.get("workflow_key"),
        "node_id": node_id,
        "trigger_event": state.get("trigger_event"),
        "target_type": state.get("target_type"),
        "target_id": state.get("target_id"),
        "inputs": dict(state.get("inputs") or {}),
        "context_payload": dict(state.get("context_payload") or {}),
        "node_outputs": dict(state.get("node_outputs") or {}),
        "artifacts": dict(state.get("artifacts") or {}),
        "approval": dict(state.get("approval_result") or {}),
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(effective_payload, ensure_ascii=False)},
    ]


def _validate_json_schema(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    if not schema:
        return
    try:
        validate_jsonschema(instance=payload, schema=schema)
    except JsonSchemaValidationError as exc:
        raise ValidationError(f"Model output does not match schema: {exc.message}") from exc


def _normalize_operation_action(state: WorkflowExecutionState, node_config: dict[str, Any]) -> tuple[str, str]:
    latest_ai = dict(_copy_artifacts(state).get("latest_ai_output") or {})
    approval = dict(state.get("approval_result") or {})
    action = (
        str(node_config.get("action") or "").strip()
        or str(approval.get("action") or "").strip()
        or str(latest_ai.get("action") or latest_ai.get("route") or "").strip()
        or "approve"
    )
    reason = (
        str(node_config.get("reason") or "").strip()
        or str(approval.get("reason") or "").strip()
        or str(latest_ai.get("summary") or "").strip()
        or "workflow_operation"
    )
    return action.lower(), reason


def _should_require_approval(
    state: WorkflowExecutionState,
    node_config: dict[str, Any],
    *,
    node_id: str,
    risk_level: str,
) -> bool:
    approval_mounts = _approval_mount_sources_for_node(state, node_id=node_id)
    if approval_mounts:
        for mount in approval_mounts:
            approval_node_id = str(mount.get("node_id") or "").strip()
            approval_payload = _node_output_payload(state, node_id=approval_node_id)
            token = dict(approval_payload.get("token") or {})
            if not bool(token.get("granted")):
                return True
        return False

    workflow_policy = dict((state.get("workflow_config") or {}).get("runtime_policy") or {})
    if risk_level != "high":
        return False
    if bool(node_config.get("allow_without_approval")):
        return False
    if bool(workflow_policy.get("allow_high_risk_without_approval")):
        return False
    token = dict(state.get("approval_token") or {})
    return not bool(token.get("granted"))


def _execute_trigger_node(
    state: WorkflowExecutionState, *, node_id: str, node_type: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    updates = _load_target_context(state)
    payload = {
        "type": node_type,
        "trigger_event": state.get("trigger_event"),
        "target_type": state.get("target_type"),
        "target_id": state.get("target_id"),
        "config": node_config,
    }
    updates["node_outputs"] = _set_node_output(state, node_id=node_id, value=payload)
    updates["execution_trace"] = _append_trace(
        state,
        node_id=node_id,
        status="completed",
        narrative="触发节点已载入上下文。",
        input_payload={"config": node_config},
        output_payload=payload,
    )
    return updates


def _execute_apply_action_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    workflow_key = str(state.get("workflow_key") or "")
    run_id = str(state.get("run_id") or "")
    surface_key = str(node_config.get("surface_key") or "").strip()
    if not surface_key:
        raise ValidationError(f"Apply Action node {node_id} is missing surface_key")
    surface = get_action_surface(surface_key, workflow_key=workflow_key)
    mount_requires_approval = _should_require_approval(
        state,
        node_config,
        node_id=node_id,
        risk_level="low",
    )
    token_granted = bool(dict(state.get("approval_token") or {}).get("granted"))
    if mount_requires_approval or (surface.requires_approval and not token_granted):
        raise ValidationError(f"Action surface requires approval: {surface_key}")

    previous_node_id = _previous_node_id(state)
    input_payload = dict((state.get("node_outputs") or {}).get(previous_node_id) or {})
    bound_values = {
        "input": input_payload,
        "agent_output": dict(_copy_artifacts(state).get("latest_ai_output") or {}),
        "approval": dict(state.get("approval_result") or {}),
        "state": state,
    }
    with get_session_factory()() as session:
        result = execute_action_surface(
            session,
            surface_key,
            workflow_key=workflow_key,
            run_id=run_id,
            input_payload=input_payload,
            bound_values=bound_values,
        )
        session.commit()
    node_info = _graph_node_payload(state, node_id=node_id)
    execution_summary = f"执行动作“{surface.label}”已完成。"
    action_source = input_payload.get("action")
    if action_source is None and isinstance(result, dict):
        action_source = result.get("action")
    action_value = str(action_source or "").strip() or None
    reason_value = str(input_payload.get("reason") or "").strip() or None
    payload = {
        "status": "success",
        "applied": True,
        "action": action_value,
        "reason": reason_value,
        "surface_key": surface_key,
        "node": {
            **node_info,
            "description": surface.description,
        },
        "execution_summary": execution_summary,
        "execution_result": result,
        "result": result,
    }
    return {
        "result_payload": payload,
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative=execution_summary,
            input_payload={"config": node_config, "input_payload": input_payload},
            output_payload=payload,
        ),
    }


def _auto_mode_fill_defaults(parsed: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Fill in missing required fields with safe type-appropriate defaults.

    Used as a last-resort fallback when the AI model fails to produce all
    required fields even after a retry (output_mode="auto").
    """
    result = dict(parsed)
    required_fields = set(schema.get("required") or [])
    properties = dict(schema.get("properties") or {})
    _type_defaults: dict[str, Any] = {
        "string": "",
        "number": 0,
        "integer": 0,
        "boolean": False,
        "object": {},
        "array": [],
    }
    for field_name in required_fields:
        if field_name in result:
            continue
        field_schema = properties.get(field_name, {})
        field_type = str(field_schema.get("type") or "string")
        result[field_name] = _type_defaults.get(field_type, "")
    return result


def _build_tool_descriptions(tool_keys: list[str], *, workflow_key: str) -> list[dict[str, Any]]:
    """Build precise tool descriptions for the AI system prompt."""
    descs: list[dict[str, Any]] = []
    for key in tool_keys:
        try:
            surface = get_tool_surface(key, workflow_key=workflow_key)
            capability_output_schema: dict[str, Any] = {"type": "object", "additionalProperties": True}
            with suppress(Exception):
                capability_output_schema = (
                    dict(get_capability_definition(kind="tool", name=surface.base_capability).output_schema or {})
                    or capability_output_schema
                )
            return_schema = (
                dict(surface.response_schema or {}) or dict(surface.output_projection or {}) or capability_output_schema
            )
            descs.append(
                {
                    "name": surface.key,
                    "label": surface.label,
                    "description": surface.description,
                    "readonly": True,
                    "domain": surface.domain,
                    "sensitivity": surface.sensitivity,
                    "parameters_schema": surface.input_schema
                    if surface.input_schema
                    else {"type": "object", "properties": {}},
                    "allowed_arguments": list(surface.allowed_args or []),
                    "auto_bound_arguments": sorted(dict(surface.bound_args or {}).keys()),
                    "fixed_arguments": dict(surface.fixed_args or {}),
                    "returns_schema": return_schema,
                    "usage_notes": dict(surface.human_card or {}),
                }
            )
        except Exception:
            continue
    return descs


def _native_model_parameters_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    candidate = dict(schema or {})
    if str(candidate.get("type") or "").strip() != "object":
        return {"type": "object", "properties": {}}
    return candidate


def _native_model_tool_description(item: dict[str, Any], *, kind: str) -> str:
    parts = [str(item.get("description") or "").strip()]
    allowed_arguments = [str(value).strip() for value in item.get("allowed_arguments") or [] if str(value).strip()]
    if allowed_arguments:
        parts.append(f"Allowed arguments: {', '.join(allowed_arguments)}.")
    auto_bound_arguments = [
        str(value).strip() for value in item.get("auto_bound_arguments") or [] if str(value).strip()
    ]
    if auto_bound_arguments:
        parts.append(
            "These arguments are auto-bound by the system and must not be supplied manually: "
            f"{', '.join(auto_bound_arguments)}."
        )
    fixed_arguments = dict(item.get("fixed_arguments") or {})
    if fixed_arguments:
        parts.append(
            f"These fixed arguments are injected automatically: {json.dumps(fixed_arguments, ensure_ascii=False)}."
        )
    if kind == "action":
        parts.append("This tool performs a state-changing action.")
    else:
        parts.append("This tool is readonly and only inspects backend state.")
    return " ".join(part for part in parts if part)


def _build_native_model_tools(
    *,
    readonly_tools: list[dict[str, Any]],
    mounted_actions: list[dict[str, Any]],
    output_schema: dict[str, Any],
    enforce_final_output_tool: bool,
) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for item in readonly_tools:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": str(item.get("name") or "").strip(),
                    "description": _native_model_tool_description(item, kind="query"),
                    "parameters": _native_model_parameters_schema(dict(item.get("parameters_schema") or {})),
                },
            }
        )
    for item in mounted_actions:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": str(item.get("key") or "").strip(),
                    "description": _native_model_tool_description(item, kind="action"),
                    "parameters": _native_model_parameters_schema(dict(item.get("parameters_schema") or {})),
                },
            }
        )
    if enforce_final_output_tool:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": FINAL_OUTPUT_TOOL_NAME,
                    "description": "Submit the final structured output for this AI task. Call this exactly once after all required capability results are available.",
                    "parameters": _native_model_parameters_schema(output_schema),
                },
            }
        )
    return [item for item in tools if str((item.get("function") or {}).get("name") or "").strip()]


def _native_tool_result_message(tool_call_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload, ensure_ascii=False),
    }


def _split_ai_output(
    raw_output: dict[str, Any],
    output_contract: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Split AI output into result (data) and route (control)."""
    route_config = output_contract.get("route") or {}
    route_field = route_config.get("field", "")

    # Extract route value
    route_value = "default"
    if route_field and route_field in raw_output:
        route_value = str(raw_output[route_field])

    # Result = everything except the route field
    result = {k: v for k, v in raw_output.items() if k != route_field and not k.startswith("__")}

    return result, route_value


def _normalize_ai_response(parsed: dict[str, Any]) -> dict[str, Any]:
    if "action" not in parsed and "proposed_action" in parsed:
        parsed["action"] = parsed.get("proposed_action")
    if "route" not in parsed and "action" in parsed:
        parsed["route"] = parsed.get("action")
    return parsed


def _tool_usage_policy(node_config: dict[str, Any]) -> tuple[str, int]:
    mode = str(node_config.get("tool_usage_mode") or "recommended").strip().lower() or "recommended"
    if mode not in {"optional", "recommended", "required"}:
        mode = "recommended"
    minimum = max(1, min(int(node_config.get("minimum_tool_calls") or 1), 10))
    return mode, minimum


def _should_enforce_final_output_tool(
    *,
    node_config: dict[str, Any],
    tool_keys: list[str],
    action_keys: list[str],
) -> bool:
    explicit = node_config.get("enforce_final_output_tool")
    if explicit is not None:
        return bool(explicit)
    return bool(tool_keys or action_keys)


def _enforce_tool_usage_policy(
    *,
    node_config: dict[str, Any],
    tool_keys: list[str],
    action_keys: list[str],
    tool_call_results: list[dict[str, Any]],
) -> None:
    if not tool_keys and not action_keys:
        return
    mode, minimum_tool_calls = _tool_usage_policy(node_config)
    if mode != "required":
        return
    successful_call_count = sum(1 for item in tool_call_results if not str(item.get("error") or "").strip())
    if successful_call_count < minimum_tool_calls:
        raise ValidationError(
            f"AI task requires at least {minimum_tool_calls} successful capability call(s) before final output."
        )


def _successful_capability_call_count(
    tool_call_results: list[dict[str, Any]],
    *,
    kinds: set[str] | None = None,
) -> int:
    return sum(
        1
        for item in tool_call_results
        if not str(item.get("error") or "").strip() and (kinds is None or str(item.get("kind") or "").strip() in kinds)
    )


def _missing_capability_correction_message(
    *,
    node_config: dict[str, Any],
    tool_keys: list[str],
    action_keys: list[str],
    tool_call_results: list[dict[str, Any]],
) -> str:
    successful_action_calls = _successful_capability_call_count(tool_call_results, kinds={"action"})
    successful_query_calls = _successful_capability_call_count(tool_call_results, kinds={"query"})
    failed_calls = [item for item in tool_call_results if str(item.get("error") or "").strip()]

    # Build a progress summary so the model knows what's already done
    progress_lines: list[str] = []
    if successful_query_calls:
        called_tools = sorted(
            {
                str(item.get("name") or "")
                for item in tool_call_results
                if item.get("kind") == "query" and not str(item.get("error") or "").strip()
            }
        )
        progress_lines.append(f"Successfully called query tools: {', '.join(called_tools)}")
    if successful_action_calls:
        called_actions = sorted(
            {
                str(item.get("name") or "")
                for item in tool_call_results
                if item.get("kind") == "action" and not str(item.get("error") or "").strip()
            }
        )
        progress_lines.append(f"Successfully called actions: {', '.join(called_actions)}")
    if failed_calls:
        failed_names = sorted({str(item.get("name") or "") for item in failed_calls})
        progress_lines.append(f"Failed calls (consider retrying with corrected arguments): {', '.join(failed_names)}")

    progress_summary = "\n".join(progress_lines) if progress_lines else "No capabilities called yet."

    if action_keys and successful_action_calls == 0:
        mounted_actions = ", ".join(action_keys)
        return (
            f"Progress so far:\n{progress_summary}\n\n"
            "You have not executed any mounted action yet. "
            f"If this task is supposed to create, update, delete, or otherwise change state, you must call one of the mounted actions now: {mounted_actions}. "
            "Do not fabricate execution_result or execution_summary without a successful mounted action result. "
            "If a previous query tool returned useful data, use it as input for the action call."
        )

    try:
        _enforce_tool_usage_policy(
            node_config=node_config,
            tool_keys=tool_keys,
            action_keys=action_keys,
            tool_call_results=tool_call_results,
        )
    except ValidationError as exc:
        available_capabilities = ", ".join(sorted(set(tool_keys) | set(action_keys)))
        return (
            f"Progress so far:\n{progress_summary}\n\n"
            f"{exc} "
            f"Available capabilities: {available_capabilities}. "
            "Call the required mounted capability now, then return the final output only after you have the real result."
        )
    return ""


def _missing_final_output_correction_message(final_output_tool_name: str) -> str:
    return (
        "You have not submitted the final output yet. "
        f"Call {final_output_tool_name} now with the final JSON object that matches the required schema. "
        "Do not reply with plain JSON."
    )


def _compact_messages_if_needed(
    messages: list[dict[str, Any]],
    *,
    max_message_count: int = 24,
    keep_recent: int = 8,
) -> list[dict[str, Any]]:
    """Compress early tool call results in message history to prevent context overflow.

    When the message list exceeds max_message_count, early tool result messages
    are replaced with a compact summary. The most recent `keep_recent` messages
    are always preserved in full for context continuity.
    """
    if len(messages) <= max_message_count:
        return messages
    # Always keep the system/first message and the most recent messages
    preserved_head = messages[:1]
    compactable = messages[1:-keep_recent]
    preserved_tail = messages[-keep_recent:]

    summary_lines: list[str] = []
    for msg in compactable:
        role = str(msg.get("role") or "").strip()
        content = str(msg.get("content") or "")[:200]
        if role == "assistant" and "tool_calls" in str(msg):
            summary_lines.append("[assistant made tool calls]")
        elif role == "user" and "capability call results" in content.lower():
            summary_lines.append("[tool results returned]")
        elif role == "user":
            summary_lines.append(f"[user: {content[:80]}...]")
        elif role == "tool":
            tool_name = str(msg.get("name") or msg.get("tool_call_id") or "")
            summary_lines.append(f"[tool result: {tool_name}]")
        else:
            summary_lines.append(f"[{role}: {content[:80]}...]")

    compact_message = {
        "role": "user",
        "content": (
            "=== Earlier conversation summary (details compacted) ===\n"
            + "\n".join(summary_lines)
            + "\n=== End of summary. Recent messages follow. ==="
        ),
    }
    return [*preserved_head, compact_message, *preserved_tail]


def _invoke_ai_task_round(
    state: WorkflowExecutionState,
    *,
    node_id: str,
    node_config: dict[str, Any],
    instructions: str,
    output_schema: dict[str, Any],
    final_output_schema: dict[str, Any] | None = None,
    user_payload: dict[str, Any],
    tool_keys: list[str],
    action_keys: list[str],
    system_prompt_override: str = "",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    enforce_final_output_tool = _should_enforce_final_output_tool(
        node_config=node_config,
        tool_keys=tool_keys,
        action_keys=action_keys,
    )
    final_output_tool_schema = dict(final_output_schema or output_schema)
    contract_context = build_ai_contract_context(
        workflow_key=str(state.get("workflow_key") or ""),
        workflow_config=dict(state.get("workflow_config") or {}),
        ai_node_id=node_id,
        node_config=node_config,
    )
    tool_descriptions = list(contract_context.get("mounted_tools") or [])
    action_descriptions = list(contract_context.get("mounted_actions") or [])
    base_system_prompt_override = system_prompt_override
    native_model_tools: list[dict[str, Any]] = []
    native_capability_tools: list[dict[str, Any]] = []
    if tool_descriptions or action_descriptions:
        tool_usage_mode, minimum_tool_calls = _tool_usage_policy(node_config)
        policy_lines = [
            "- When the task depends on current backend state, lists, counts, statuses, recent activity, diagnostics, configuration, visitors, subscriptions, backups, or automation runtime data, call the relevant tool before answering.",
            "- Prefer tool-grounded answers over assumptions whenever a relevant tool is available.",
            "- Do not guess current admin or workflow state if it can be verified with a tool.",
        ]
        if tool_usage_mode == "required":
            policy_lines.append(
                f"- For this node, mounted capabilities are required. Before final output, make at least {minimum_tool_calls} successful capability call(s)."
            )
        elif tool_usage_mode == "recommended":
            policy_lines.append(
                "- For this node, mounted tools are strongly recommended whenever they can reduce uncertainty."
            )
        capability_rules = [
            "- Use only the capability names listed below.",
            "- Pass arguments as a JSON object.",
            "- Only include arguments that appear in allowed_arguments or parameters_schema.",
            "- Arguments shown in fixed_arguments or auto_bound_arguments are handled by the system; do not invent extra values for them.",
        ]
        if tool_descriptions:
            capability_rules.append("- Readonly query tools can inspect backend state without changing anything.")
        if action_descriptions:
            capability_rules.append(
                "- Mounted action tools can perform write/execution operations. Use them only when they are truly needed."
            )
        if enforce_final_output_tool:
            capability_rules.append(
                f"- When your final answer is ready, call {FINAL_OUTPUT_TOOL_NAME} exactly once with the final JSON payload."
            )
        legacy_tools_block = (
            "You have access to the following mounted capabilities.\n"
            "Capability rules:\n"
            f"{chr(10).join(capability_rules)}\n"
            f"{chr(10).join(policy_lines)}\n"
            "- After capability results are returned, produce final JSON that matches the required output schema.\n\n"
            "Readonly tools:\n"
            f"{json.dumps(tool_descriptions, ensure_ascii=False)}\n\n"
            "Mounted actions:\n"
            f"{json.dumps(action_descriptions, ensure_ascii=False)}\n\n"
            "Final output tool:\n"
            f"{json.dumps({'name': FINAL_OUTPUT_TOOL_NAME, 'description': 'Submit the final structured output for this AI task.', 'parameters_schema': final_output_tool_schema}, ensure_ascii=False)}\n\n"
            'To call any mounted capability, include a "tool_calls" array in your response:\n'
            '[{"name": "capability_name", "arguments": {...}}]'
        )
        native_tools_block = (
            "You have access to the following mounted capabilities.\n"
            "Capability rules:\n"
            f"{chr(10).join(capability_rules)}\n"
            f"{chr(10).join(policy_lines)}\n"
            "- Use native tool/function calling for mounted capabilities instead of embedding tool_calls inside JSON content.\n"
            "- After capability results are returned, either call more mounted capabilities or submit the final output tool.\n\n"
            "Readonly tools:\n"
            f"{json.dumps(tool_descriptions, ensure_ascii=False)}\n\n"
            "Mounted actions:\n"
            f"{json.dumps(action_descriptions, ensure_ascii=False)}\n\n"
            "Final output tool:\n"
            f"{json.dumps({'name': FINAL_OUTPUT_TOOL_NAME, 'description': 'Submit the final structured output for this AI task.', 'parameters_schema': final_output_tool_schema}, ensure_ascii=False)}"
        )
        native_capability_tools = _build_native_model_tools(
            readonly_tools=tool_descriptions,
            mounted_actions=action_descriptions,
            output_schema=final_output_tool_schema,
            enforce_final_output_tool=False,
        )
        native_model_tools = _build_native_model_tools(
            readonly_tools=tool_descriptions,
            mounted_actions=action_descriptions,
            output_schema=final_output_tool_schema,
            enforce_final_output_tool=enforce_final_output_tool,
        )
    else:
        legacy_tools_block = ""
        native_tools_block = ""

    model_config = _ai_model_config(state, node_config)
    mounted_action_names = {
        str(item.get("key") or "").strip() for item in action_descriptions if str(item.get("key") or "").strip()
    }
    if not mounted_action_names and action_keys:
        mounted_action_names = {
            item.key
            for item in list_action_surface_invocations(
                str(state.get("workflow_key") or ""),
                surface_keys=action_keys,
            )
        }
    mounted_capability_names = set(tool_keys) | mounted_action_names

    def _system_override(block: str) -> str:
        if not block:
            return base_system_prompt_override
        return f"{base_system_prompt_override}\n\n{block}" if base_system_prompt_override.strip() else block

    def _native_round_controls(
        tool_call_results: list[dict[str, Any]],
        *,
        awaiting_final_output: bool,
    ) -> tuple[list[dict[str, Any]], str]:
        missing_capability = bool(
            _missing_capability_correction_message(
                node_config=node_config,
                tool_keys=tool_keys,
                action_keys=action_keys,
                tool_call_results=tool_call_results,
            )
        )
        if missing_capability:
            return native_capability_tools, "required"
        if enforce_final_output_tool and awaiting_final_output and (tool_call_results or not mounted_capability_names):
            return native_model_tools, "required"
        return native_model_tools, "auto"

    def _invoke_round_model(
        messages: list[dict[str, Any]],
        *,
        native: bool,
        native_tools: list[dict[str, Any]] | None = None,
        native_tool_choice: str | None = None,
    ) -> _ModelTurnResult:
        if native:
            return _invoke_model_turn(
                model_config,
                messages=messages,
                tools=native_tools or native_model_tools,
                tool_choice=native_tool_choice,
            )
        return _invoke_model_turn(model_config, messages=messages, require_json_object=True)

    def _legacy_assistant_echo(turn: _ModelTurnResult, parsed_payload: dict[str, Any]) -> dict[str, Any]:
        raw_content = str(turn["raw_content"] or "").strip()
        if raw_content:
            return {"role": "assistant", "content": raw_content}
        return {"role": "assistant", "content": json.dumps(parsed_payload, ensure_ascii=False)}

    tool_protocol = "legacy"
    if native_model_tools:
        native_messages = _build_ai_messages(
            state,
            instructions=instructions,
            output_schema=output_schema,
            node_id=node_id,
            contract_context=contract_context,
            system_prompt_override=_system_override(native_tools_block),
            user_payload=user_payload,
        )
        try:
            initial_native_tools, initial_native_tool_choice = _native_round_controls(
                [],
                awaiting_final_output=enforce_final_output_tool,
            )
            turn = _invoke_round_model(
                native_messages,
                native=True,
                native_tools=initial_native_tools,
                native_tool_choice=initial_native_tool_choice,
            )
            messages = native_messages
            tool_protocol = "native"
        except _NativeToolCallingUnsupportedError:
            messages = _build_ai_messages(
                state,
                instructions=instructions,
                output_schema=output_schema,
                node_id=node_id,
                contract_context=contract_context,
                system_prompt_override=_system_override(legacy_tools_block),
                user_payload=user_payload,
            )
            turn = _invoke_round_model(messages, native=False)
    else:
        messages = _build_ai_messages(
            state,
            instructions=instructions,
            output_schema=output_schema,
            node_id=node_id,
            contract_context=contract_context,
            system_prompt_override=base_system_prompt_override,
            user_payload=user_payload,
        )
        if not (mounted_capability_names or enforce_final_output_tool):
            return _normalize_ai_response(_invoke_model_json(model_config, messages=messages)), []
        turn = _invoke_round_model(messages, native=False)

    parsed = _normalize_ai_response(dict(turn["parsed_content"] or {}))

    # ── Mounted capability loop: each call returns results before the next round ──
    tool_call_results: list[dict[str, Any]] = []
    final_output_payload: dict[str, Any] | None = None
    capability_turn = 0
    max_capability_turns = max(1, min(int(node_config.get("max_capability_turns") or 12), 30))
    correction_turn = 0
    max_correction_turns = max(1, min(int(node_config.get("max_correction_turns") or 3), 5))
    while mounted_capability_names or enforce_final_output_tool:
        ai_tool_calls: list[dict[str, Any]] = []
        if turn["tool_calls"]:
            ai_tool_calls = [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "arguments": dict(item["arguments"]),
                }
                for item in turn["tool_calls"]
            ]
        else:
            legacy_tool_calls = parsed.get("tool_calls")
            if isinstance(legacy_tool_calls, list):
                ai_tool_calls = [dict(item) for item in legacy_tool_calls if isinstance(item, dict)]
        native_turn_protocol = tool_protocol == "native" and bool(turn["tool_calls"])
        if not ai_tool_calls:
            correction_message = _missing_capability_correction_message(
                node_config=node_config,
                tool_keys=tool_keys,
                action_keys=action_keys,
                tool_call_results=tool_call_results,
            )
            if not correction_message and enforce_final_output_tool and final_output_payload is None:
                correction_message = _missing_final_output_correction_message(FINAL_OUTPUT_TOOL_NAME)
            # On the last correction attempt, add a stronger hint
            if correction_message and correction_turn == max_correction_turns - 1:
                correction_message += (
                    "\n\nThis is your LAST chance to call the required capabilities. "
                    "Review the available tools carefully and make the call now."
                )
            if correction_message and correction_turn < max_correction_turns:
                correction_turn += 1
                if native_turn_protocol:
                    messages.append(dict(turn["assistant_message"]))
                else:
                    messages.append(_legacy_assistant_echo(turn, parsed))
                messages.append({"role": "user", "content": correction_message})
                if tool_protocol == "native":
                    next_native_tools, next_native_tool_choice = _native_round_controls(
                        tool_call_results,
                        awaiting_final_output=final_output_payload is None,
                    )
                    turn = _invoke_round_model(
                        messages,
                        native=True,
                        native_tools=next_native_tools,
                        native_tool_choice=next_native_tool_choice,
                    )
                else:
                    turn = _invoke_round_model(messages, native=False)
                parsed = _normalize_ai_response(dict(turn["parsed_content"] or {}))
                continue
            break
        capability_turn += 1
        if capability_turn > max_capability_turns:
            raise ValidationError(
                f"AI exceeded the mounted capability call limit ({max_capability_turns}) within one round."
            )

        current_batch_results: list[dict[str, Any]] = []
        pending_final_output: dict[str, Any] | None = None
        legacy_followup_notes: list[str] = []
        native_tool_messages: list[dict[str, Any]] = []
        has_non_final_tool_call = any(
            str(item.get("name") or "").strip() and str(item.get("name") or "").strip() != FINAL_OUTPUT_TOOL_NAME
            for item in ai_tool_calls
        )
        if has_non_final_tool_call:
            final_output_payload = None
        bound_values = {
            "input": user_payload,
            "agent_output": parsed,
            "capability_results": tool_call_results,
            "latest_capability_results": current_batch_results,
            "state": state,
        }
        with get_session_factory()() as session:
            for tc in ai_tool_calls:
                tool_name = str(tc.get("name") or "").strip()
                tool_args = dict(tc.get("arguments") or {})
                tool_call_id = str(tc.get("id") or "").strip()
                if not tool_name:
                    continue
                if enforce_final_output_tool and tool_name == FINAL_OUTPUT_TOOL_NAME:
                    if has_non_final_tool_call:
                        note = (
                            f"{FINAL_OUTPUT_TOOL_NAME} was ignored because capability results arrived in the same round. "
                            f"Review the real results and call {FINAL_OUTPUT_TOOL_NAME} again after that."
                        )
                        legacy_followup_notes.append(note)
                        if native_turn_protocol and tool_call_id:
                            native_tool_messages.append(
                                _native_tool_result_message(
                                    tool_call_id,
                                    {
                                        "status": "error",
                                        "error": "final_output_requires_latest_tool_results",
                                        "message": note,
                                    },
                                )
                            )
                        continue
                    try:
                        _validate_json_schema(tool_args, final_output_tool_schema)
                    except ValidationError as exc:
                        note = str(exc)
                        legacy_followup_notes.append(note)
                        if native_turn_protocol and tool_call_id:
                            native_tool_messages.append(
                                _native_tool_result_message(
                                    tool_call_id,
                                    {
                                        "status": "error",
                                        "error": "invalid_final_output",
                                        "message": note,
                                    },
                                )
                            )
                        continue
                    pending_final_output = tool_args
                    continue
                try:
                    if tool_name in mounted_action_names:
                        surface = get_action_surface_invocation(
                            tool_name, workflow_key=str(state.get("workflow_key") or "")
                        )
                        if surface.requires_approval and not bool(
                            dict(state.get("approval_token") or {}).get("granted")
                        ):
                            raise ValidationError(f"Mounted action requires approval: {tool_name}")
                        result = execute_action_surface(
                            session,
                            tool_name,
                            workflow_key=str(state.get("workflow_key") or ""),
                            run_id=str(state.get("run_id") or ""),
                            input_payload=tool_args,
                            bound_values=bound_values,
                        )
                        current_batch_results.append({"name": tool_name, "kind": "action", "result": result})
                        if native_turn_protocol and tool_call_id:
                            native_tool_messages.append(
                                _native_tool_result_message(
                                    tool_call_id,
                                    {"status": "success", "kind": "action", "result": result},
                                )
                            )
                    elif tool_name in tool_keys:
                        result = execute_tool_surface(
                            session,
                            tool_name,
                            workflow_key=str(state.get("workflow_key") or ""),
                            run_id=str(state.get("run_id") or ""),
                            agent_args=tool_args,
                            bound_values=bound_values,
                        )
                        current_batch_results.append({"name": tool_name, "kind": "query", "result": result})
                        if native_turn_protocol and tool_call_id:
                            native_tool_messages.append(
                                _native_tool_result_message(
                                    tool_call_id,
                                    {"status": "success", "kind": "query", "result": result},
                                )
                            )
                    else:
                        current_batch_results.append({"name": tool_name, "error": "not_mounted"})
                        if native_turn_protocol and tool_call_id:
                            native_tool_messages.append(
                                _native_tool_result_message(
                                    tool_call_id,
                                    {
                                        "status": "error",
                                        "error": "not_mounted",
                                        "message": f"Mounted capability {tool_name} is not available in this node.",
                                    },
                                )
                            )
                except Exception as exc:
                    logger.warning(
                        "Mounted capability execution failed for %s in node %s",
                        tool_name,
                        node_id,
                        exc_info=True,
                    )
                    message = str(exc).strip() or exc.__class__.__name__
                    current_batch_results.append(
                        {
                            "name": tool_name,
                            "error": "execution_failed",
                            "error_type": exc.__class__.__name__,
                            "message": message[:280],
                        }
                    )
                    if native_turn_protocol and tool_call_id:
                        native_tool_messages.append(
                            _native_tool_result_message(
                                tool_call_id,
                                {
                                    "status": "error",
                                    "error": "execution_failed",
                                    "error_type": exc.__class__.__name__,
                                    "message": message[:280],
                                },
                            )
                        )
            session.commit()

        if pending_final_output is not None and not current_batch_results:
            final_output_payload = pending_final_output
            break

        tool_call_results.extend(current_batch_results)
        # Compact message history if it's getting too long
        messages = _compact_messages_if_needed(messages)
        if native_turn_protocol:
            messages.append(dict(turn["assistant_message"]))
            messages.extend(native_tool_messages)
            next_native_tools, next_native_tool_choice = _native_round_controls(
                tool_call_results,
                awaiting_final_output=final_output_payload is None,
            )
            turn = _invoke_round_model(
                messages,
                native=True,
                native_tools=next_native_tools,
                native_tool_choice=next_native_tool_choice,
            )
        else:
            messages.append(_legacy_assistant_echo(turn, parsed))
            followup_content = (
                "Mounted capability call results:\n"
                f"{json.dumps(current_batch_results, ensure_ascii=False)}\n\n"
                "You may now decide the next mounted capability call, or return the final JSON response if everything is ready."
            )
            if legacy_followup_notes:
                followup_content = f"{followup_content}\n\n" + "\n".join(legacy_followup_notes)
            messages.append({"role": "user", "content": followup_content})
            turn = _invoke_round_model(messages, native=False)
        parsed = _normalize_ai_response(dict(turn["parsed_content"] or {}))

    if enforce_final_output_tool:
        if final_output_payload is None:
            raise ValidationError(f"AI task did not submit final output via {FINAL_OUTPUT_TOOL_NAME}.")
        parsed = dict(final_output_payload)

    return parsed, tool_call_results


def _execute_ai_task_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    instructions = str(node_config.get("instructions") or node_config.get("prompt") or "").strip()
    mode = str(node_config.get("mode") or "direct").strip().lower() or "direct"
    output_schema = _ai_output_schema(node_config, node_id=node_id, state=state)
    ai_input = _ai_input_payload(state, node_config, node_id=node_id)

    graph = dict((state.get("workflow_config") or {}).get("graph") or {})
    graph_nodes = [dict(item) for item in graph.get("nodes") or [] if isinstance(item, dict)]
    graph_edges = [dict(item) for item in graph.get("edges") or [] if isinstance(item, dict)]
    tool_keys = mounted_tool_surface_keys(graph_nodes, graph_edges, ai_node_id=node_id)
    action_keys = mounted_action_surface_keys(graph_nodes, graph_edges, ai_node_id=node_id)

    artifacts = _copy_artifacts(state)
    tool_call_results: list[dict[str, Any]] = []

    if mode == "loop":
        max_rounds = max(1, min(int(node_config.get("loop_max_rounds") or 6), 20))
        notebook: list[dict[str, Any]] = []
        parsed: dict[str, Any] | None = None
        loop_schema = {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Your step-by-step thought process before deciding whether to continue.",
                },
                "continue_loop": {"type": "boolean"},
                "note_for_next_round": {"type": "string"},
                "final_output": output_schema,
            },
            "required": ["reasoning", "continue_loop", "note_for_next_round", "final_output"],
        }
        loop_final_output_schema = {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Optional notebook reasoning for this loop round.",
                },
                "continue_loop": {"type": "boolean"},
                "note_for_next_round": {"type": "string"},
                "final_output": output_schema,
            },
            "required": ["continue_loop", "final_output"],
        }
        loop_instruction = (
            "You are in loop mode. Your job is to iteratively use tools and refine your answer.\n\n"
            "IMPORTANT RULES:\n"
            "1. Each round, first review the notebook to understand what you've done so far.\n"
            "2. If you need more information, call the appropriate mounted capabilities.\n"
            "3. Set continue_loop=true when:\n"
            "   - You just called tools and need to process or verify results\n"
            "   - You haven't met the minimum required capability calls\n"
            "   - Your final_output is incomplete or needs data from another tool\n"
            "4. Set continue_loop=false ONLY when:\n"
            "   - final_output fully answers the task with real data from tools\n"
            "   - All required capability calls have been made successfully\n"
            "   - You've verified the output against the schema\n"
            "5. Use note_for_next_round to leave yourself breadcrumbs about what to do next.\n"
            "6. Use reasoning to explain your thought process before deciding whether to continue.\n"
            "7. NEVER fabricate data — if a tool call failed, retry or adjust your approach.\n"
        )
        last_error = ""
        accumulated_observations: list[dict[str, Any]] = []
        for round_index in range(1, max_rounds + 1):
            # Carry forward previous round's tool results for context continuity
            previous_tool_results = tool_call_results[-5:] if tool_call_results else []
            round_payload = {
                "task_inputs": ai_input,
                "loop": {
                    "round_index": round_index,
                    "max_rounds": max_rounds,
                    "notebook": notebook,
                    "last_error": last_error,
                    "previous_tool_results": previous_tool_results,
                    "accumulated_observations": accumulated_observations[-10:],
                    "total_successful_tool_calls": sum(
                        1 for r in tool_call_results if not str(r.get("error") or "").strip()
                    ),
                },
            }
            round_parsed, tool_call_results = _invoke_ai_task_round(
                state,
                node_id=node_id,
                node_config=node_config,
                instructions=instructions,
                output_schema=loop_schema,
                final_output_schema=loop_final_output_schema,
                user_payload=round_payload,
                tool_keys=tool_keys,
                action_keys=action_keys,
                system_prompt_override=loop_instruction,
            )
            continue_loop = bool(round_parsed.get("continue_loop"))
            note_for_next_round = str(round_parsed.get("note_for_next_round") or "").strip()
            reasoning = str(round_parsed.get("reasoning") or "").strip()
            final_output = dict(round_parsed.get("final_output") or {})
            # Accumulate observations from this round's tool calls
            for tcr in tool_call_results:
                if not str(tcr.get("error") or "").strip():
                    accumulated_observations.append(
                        {
                            "round": round_index,
                            "tool": str(tcr.get("name") or ""),
                            "kind": str(tcr.get("kind") or ""),
                        }
                    )
            try:
                _enforce_tool_usage_policy(
                    node_config=node_config,
                    tool_keys=tool_keys,
                    action_keys=action_keys,
                    tool_call_results=tool_call_results,
                )
                _validate_json_schema(final_output, output_schema)
                notebook.append(
                    {
                        "round_index": round_index,
                        "reasoning": reasoning,
                        "continue_loop": continue_loop,
                        "note_for_next_round": note_for_next_round,
                        "final_output": final_output,
                        "tool_call_results": tool_call_results,
                    }
                )
                if not continue_loop:
                    parsed = final_output
                    break
                last_error = ""
            except ValidationError as exc:
                last_error = str(exc)
                notebook.append(
                    {
                        "round_index": round_index,
                        "reasoning": reasoning,
                        "continue_loop": True,
                        "note_for_next_round": note_for_next_round,
                        "final_output": final_output,
                        "tool_call_results": tool_call_results,
                        "validation_error": last_error,
                    }
                )
                continue
        if parsed is None:
            raise ValidationError("AI loop mode did not converge to a valid final_output within max rounds.")
        artifacts["ai_loop_notebook"] = notebook
    else:
        parsed, tool_call_results = _invoke_ai_task_round(
            state,
            node_id=node_id,
            node_config=node_config,
            instructions=instructions,
            output_schema=output_schema,
            user_payload=ai_input,
            tool_keys=tool_keys,
            action_keys=action_keys,
        )
        _enforce_tool_usage_policy(
            node_config=node_config,
            tool_keys=tool_keys,
            action_keys=action_keys,
            tool_call_results=tool_call_results,
        )
        _validate_json_schema(parsed, output_schema)

    # ── Output contract: split data vs control ──
    output_contract = node_config.get("output_contract")
    if isinstance(output_contract, dict):
        result_data, route_value = _split_ai_output(parsed, output_contract)
    else:
        # Legacy path: keep full parsed as result, derive route as before
        result_data = parsed
        route_path = str(node_config.get("route_path") or "").strip()
        route_value = (_lookup_path(parsed, route_path) if route_path else parsed.get("route")) or "default"

    artifacts["latest_ai_output"] = parsed
    # Store result (data only, no route field) in node_outputs;
    # set __route__ from the separated route value.
    payload = {
        **result_data,
        "__route__": str(route_value),
    }
    if tool_call_results:
        payload["__tool_call_results__"] = tool_call_results
    loop_notebook = artifacts.get("ai_loop_notebook")
    if isinstance(loop_notebook, list) and loop_notebook:
        payload["__loop_notebook__"] = loop_notebook
    # Add loop progress metadata to artifacts
    if mode == "loop" and notebook:
        total_tool_calls = sum(len(entry.get("tool_call_results") or []) for entry in notebook)
        successful_tool_calls = sum(
            1
            for entry in notebook
            for tcr in (entry.get("tool_call_results") or [])
            if not str(tcr.get("error") or "").strip()
        )
        artifacts["ai_loop_progress"] = {
            "rounds_completed": len(notebook),
            "max_rounds": max_rounds if mode == "loop" else None,
            "total_tool_calls": total_tool_calls,
            "successful_tool_calls": successful_tool_calls,
            "converged": parsed is not None,
        }

    return {
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "artifacts": artifacts,
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="AI 节点已完成执行。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _execute_condition_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    expression = str(node_config.get("expression") or "").strip()
    result = _evaluate_condition_expression(expression, state)
    payload = {"expression": expression, "result": result}
    return {
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="条件节点已完成判断。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _execute_delay_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    delay_seconds = int(node_config.get("delay_seconds") or 0)
    until_path = str(node_config.get("until_path") or "").strip()
    until_raw = _lookup_path(_condition_environment(state), until_path) if until_path else None
    if isinstance(until_raw, str) and until_raw:
        try:
            resume_at = datetime.fromisoformat(until_raw)
        except ValueError as exc:
            raise ValidationError(f"Invalid delay until timestamp: {until_raw}") from exc
    else:
        resume_at = shanghai_now() + timedelta(seconds=max(delay_seconds, 1))
    response = interrupt(
        {
            "kind": "wait",
            "wait_type": "delay",
            "node_id": node_id,
            "resume_at": format_beijing_iso_datetime(resume_at),
        }
    )
    payload = {
        "resumed_at": str(dict(response or {}).get("resumed_at") or format_beijing_iso_datetime(shanghai_now())),
    }
    return {
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="延时节点已恢复执行。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _execute_wait_for_event_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    timeout_seconds = int(node_config.get("timeout_seconds") or 3600)
    response = interrupt(
        {
            "kind": "wait",
            "wait_type": "event",
            "node_id": node_id,
            "event_type": str(node_config.get("event_type") or "").strip(),
            "target_type": str(node_config.get("target_type") or "").strip() or None,
            "timeout_at": format_beijing_iso_datetime(shanghai_now() + timedelta(seconds=max(timeout_seconds, 1))),
        }
    )
    response_payload = dict(response or {})
    if response_payload.get("timeout"):
        payload = {"status": "timeout"}
    else:
        payload = {
            "status": "matched",
            "event": dict(response_payload.get("event") or {}),
        }
    return {
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="等待事件节点已恢复执行。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _poll_success(node_config: dict[str, Any], result: Any, state: WorkflowExecutionState) -> bool:
    expression = str(node_config.get("success_expression") or "").strip()
    if not expression:
        return bool(result)
    env = _condition_environment(state)
    env["poll_result"] = result
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValidationError(f"Invalid poll success expression: {expression}") from exc
    return bool(_eval_expr(tree.body, env))


def _execute_poll_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    interval_seconds = int(node_config.get("interval_seconds") or 60)
    max_attempts = int(node_config.get("max_attempts") or 10)
    operation_type = str(node_config.get("operation_type") or "capability").strip() or "capability"
    operation_key = str(node_config.get("operation_key") or "").strip()
    argument_mappings = list(node_config.get("argument_mappings") or [])
    attempt = 1
    while True:
        with get_session_factory()() as session:
            result = execute_operation(
                session,
                operation_type=operation_type,
                key=operation_key,
                arguments=_resolve_argument_mappings(state, argument_mappings, defaults={}),
            )
            session.commit()
        if _poll_success(node_config, result, state):
            payload = {"status": "done", "attempt": attempt, "result": result}
            return {
                "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
                "execution_trace": _append_trace(
                    state,
                    node_id=node_id,
                    status="completed",
                    narrative="轮询节点已满足条件。",
                    input_payload={"config": node_config, "attempt": attempt},
                    output_payload=payload,
                ),
            }
        if attempt >= max_attempts:
            payload = {"status": "timeout", "attempt": attempt, "result": result}
            return {
                "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
                "execution_trace": _append_trace(
                    state,
                    node_id=node_id,
                    status="failed",
                    narrative="轮询节点已达到最大尝试次数。",
                    input_payload={"config": node_config, "attempt": attempt},
                    output_payload=payload,
                ),
            }
        resume = interrupt(
            {
                "kind": "wait",
                "wait_type": "poll",
                "node_id": node_id,
                "resume_at": format_beijing_iso_datetime(shanghai_now() + timedelta(seconds=max(interval_seconds, 1))),
                "attempt": attempt + 1,
            }
        )
        attempt = int(dict(resume or {}).get("attempt") or (attempt + 1))


def _execute_approval_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    latest_ai = dict(_copy_artifacts(state).get("latest_ai_output") or {})
    mode = str(node_config.get("mode") or "conditional").strip().lower()
    force = bool(node_config.get("force"))
    required_from_path = str(node_config.get("required_from_path") or "").strip()
    should_require = force or mode == "always"
    if mode == "conditional" and required_from_path:
        should_require = should_require or bool(_lookup_path(latest_ai, required_from_path))
    if mode == "never":
        should_require = False

    if should_require:
        response = interrupt(
            {
                "kind": "approval",
                "node_id": node_id,
                "approval_type": str(node_config.get("approval_type") or "manual_review"),
                "message": _lookup_path(latest_ai, str(node_config.get("message_path") or "summary"))
                or latest_ai.get("summary")
                or "需要人工审批。",
                "proposed_action": latest_ai.get("action") or latest_ai.get("route") or "approve",
                "payload": latest_ai,
            }
        )
        decision = dict(response or {})
        token = {
            "granted": decision.get("action") != "reject",
            "approval_type": str(node_config.get("approval_type") or "manual_review"),
            "reviewed_at": format_beijing_iso_datetime(shanghai_now()),
        }
        payload = {"decision": decision, "token": token}
    else:
        decision = {"action": latest_ai.get("action") or "approve"}
        token = {
            "granted": True,
            "approval_type": str(node_config.get("approval_type") or "manual_review"),
            "auto": True,
        }
        payload = {"decision": decision, "token": token}
    return {
        "approval_result": decision,
        "approval_token": token,
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="审批节点已完成。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _operation_defaults(state: WorkflowExecutionState, node_config: dict[str, Any]) -> dict[str, Any]:
    action, reason = _normalize_operation_action(state, node_config)
    payload = {
        "action": action,
        "reason": reason,
        "target_id": str(state.get("target_id") or "").strip(),
        "workflow_key": state.get("workflow_key"),
        "run_id": state.get("run_id"),
    }
    target_type = str(state.get("target_type") or "").strip()
    if target_type == "comment":
        payload["comment_id"] = payload["target_id"]
    elif target_type == "guestbook":
        payload["entry_id"] = payload["target_id"]
    elif target_type == "content":
        payload["content_id"] = payload["target_id"]
        payload["item_id"] = payload["target_id"]
    return payload


def _validate_operation_arguments(
    definition: AutomationOperationDefinition,
    arguments: dict[str, Any],
    *,
    node_id: str,
) -> None:
    schema = definition.input_schema
    if not schema or not isinstance(schema, dict):
        return
    properties = schema.get("properties") or {}
    required_fields: list[str] = list(schema.get("required") or [])
    missing = [field for field in required_fields if field not in arguments or arguments[field] is None]
    if missing:
        msg = (
            f"Operation node '{node_id}' ({definition.key}): missing required argument(s): {', '.join(sorted(missing))}"
        )
        logger.error(msg)
        raise ValidationError(msg)
    for field_name, field_value in arguments.items():
        if field_value is None:
            continue
        field_schema = properties.get(field_name)
        if not isinstance(field_schema, dict):
            continue
        expected_type_name = field_schema.get("type")
        if not expected_type_name or expected_type_name not in _JSONSCHEMA_TYPE_MAP:
            continue
        expected_type = _JSONSCHEMA_TYPE_MAP[expected_type_name]
        if not isinstance(field_value, expected_type):
            logger.warning(
                "Operation node '%s' (%s): argument '%s' expected type '%s' but got '%s'",
                node_id,
                definition.key,
                field_name,
                expected_type_name,
                type(field_value).__name__,
            )


def _execute_operation_node(
    state: WorkflowExecutionState, *, node_id: str, node_type: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    operation_type = node_type.split(".", 1)[1]
    operation_key = str(node_config.get("operation_key") or node_config.get("capability") or "").strip()
    if not operation_key:
        raise ValidationError(f"Operation node {node_id} is missing operation_key")
    definition = get_operation_definition(operation_type=operation_type, key=operation_key)
    risk_level = str(node_config.get("risk_level") or definition.risk_level).strip().lower() or "low"
    if _should_require_approval(state, node_config, node_id=node_id, risk_level=risk_level):
        raise ValidationError(f"High-risk operation requires approval: {operation_key}")

    defaults = _operation_defaults(state, node_config)
    arguments = _resolve_argument_mappings(state, list(node_config.get("argument_mappings") or []), defaults=defaults)
    _validate_operation_arguments(definition, arguments, node_id=node_id)
    executed_operation_key = operation_key
    if operation_key == "moderate_comment | moderate_guestbook_entry":
        if str(arguments.get("comment_id") or "").strip():
            executed_operation_key = "moderate_comment"
        elif str(arguments.get("entry_id") or "").strip():
            executed_operation_key = "moderate_guestbook_entry"
    action = str(arguments.get("action") or "").strip().lower()
    fallback_mode = str(node_config.get("fallback_mode") or "").strip()
    if (
        fallback_mode == "pending_on_ai_reject"
        and action == "reject"
        and operation_key
        in {"moderate_comment", "moderate_guestbook_entry", "moderate_comment | moderate_guestbook_entry"}
        and bool(dict(state.get("approval_token") or {}).get("auto"))
    ):
        node_info = _graph_node_payload(state, node_id=node_id)
        payload = {
            "status": "pending",
            "applied": False,
            "action": "pending",
            "reason": arguments.get("reason"),
            "node": {
                **node_info,
                "description": definition.description,
            },
            "execution_summary": "高风险拒绝动作已自动转为人工复核。",
            "execution_result": {
                "status": "pending",
                "reason": arguments.get("reason"),
            },
            "execution": {
                "operation_type": operation_type,
                "operation_key": "moderation_deferred",
                "capability": "moderation_deferred",
                "arguments": arguments,
            },
        }
        return {
            "result_payload": payload,
            "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
            "execution_trace": _append_trace(
                state,
                node_id=node_id,
                status="completed",
                narrative="高风险拒绝动作已自动转为人工复核。",
                input_payload={"config": node_config, "arguments": arguments},
                output_payload=payload,
            ),
        }

    with get_session_factory()() as session:
        result = execute_operation(
            session,
            operation_type=operation_type,
            key=operation_key,
            arguments={key: value for key, value in arguments.items() if value is not None},
        )
        session.commit()
    node_info = _graph_node_payload(state, node_id=node_id)
    execution_summary = f"平台能力“{definition.label}”已执行。"
    payload = {
        "status": "success",
        "applied": True,
        "action": arguments.get("action"),
        "reason": arguments.get("reason"),
        "node": {
            **node_info,
            "description": definition.description,
        },
        "execution_summary": execution_summary,
        "execution_result": result,
        "execution": {
            "operation_type": operation_type,
            "operation_key": operation_key,
            "capability": executed_operation_key,
            "risk_level": risk_level,
            "arguments": arguments,
            "result": result,
        },
    }
    return {
        "result_payload": payload,
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative=execution_summary,
            input_payload={"config": node_config, "arguments": arguments},
            output_payload=payload,
        ),
    }


def _queue_webhook_deliveries(
    state: WorkflowExecutionState, node_config: dict[str, Any], *, node_id: str
) -> dict[str, Any]:
    linked_ids = node_config.get("linked_subscription_ids")
    subscription_ids = [item for item in linked_ids if isinstance(item, str)] if isinstance(linked_ids, list) else []

    # Find the direct upstream node to trim the payload
    upstream_node_id = None
    graph_edges = (state.get("workflow_config") or {}).get("graph", {}).get("edges", [])
    for edge in graph_edges:
        if isinstance(edge, dict) and edge.get("target") == node_id:
            upstream_node_id = edge.get("source")
            break

    upstream_output: dict[str, Any] = {}
    formatted_text = ""
    if upstream_node_id:
        upstream_output = dict((state.get("node_outputs") or {}).get(upstream_node_id, {}))
        formatted_text = _build_webhook_formatted_text(upstream_output)

    event = AutomationEvent(
        event_type=str(node_config.get("event_type") or state.get("trigger_event") or "workflow.graph"),
        event_id=hashlib.sha256(f"{state.get('run_id')}:{node_config}".encode()).hexdigest()[:32],
        target_type=str(state.get("target_type") or "workflow"),
        target_id=str(state.get("target_id") or state.get("workflow_key") or "workflow"),
        payload={
            "run_id": state.get("run_id"),
            "workflow_key": state.get("workflow_key"),
            "data": upstream_output,
            "formatted_text": formatted_text,
        },
    )
    delivery_count = 0
    with get_session_factory()() as session:
        for subscription_id in subscription_ids:
            subscription = repo.get_webhook_subscription(session, subscription_id)
            if subscription is None or subscription.status != "active":
                continue
            repo.create_webhook_delivery(session, subscription=subscription, event=event)
            delivery_count += 1
        session.commit()
    return {
        "status": "completed",
        "delivery_count": delivery_count,
        "event_type": event.event_type,
        "formatted_text": formatted_text,
    }


def _execute_notification_webhook_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    payload = _queue_webhook_deliveries(state, node_config, node_id=node_id)
    return {
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="Webhook 通知节点已完成。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _execute_tool_mount_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    payload: dict[str, Any] = {}
    return {
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="工具挂载节点已跳过执行。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _execute_note_node(
    state: WorkflowExecutionState, *, node_id: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    payload = {
        "status": "noted",
        "content": str(node_config.get("content") or "").strip(),
    }
    return {
        "node_outputs": _set_node_output(state, node_id=node_id, value=payload),
        "execution_trace": _append_trace(
            state,
            node_id=node_id,
            status="completed",
            narrative="备注节点已记录说明。",
            input_payload={"config": node_config},
            output_payload=payload,
        ),
    }


def _execute_graph_node(
    state: WorkflowExecutionState, *, node_id: str, node_type: str, node_config: dict[str, Any]
) -> WorkflowExecutionState:
    normalized_type = normalize_node_type(node_type)
    effective_state = state
    if normalized_type != "approval.review":
        approval_updates = _ensure_mounted_approval_tokens(state, node_id=node_id)
        if approval_updates:
            effective_state = _state_with_updates(state, approval_updates)

    if normalized_type.startswith("trigger."):
        return _execute_trigger_node(
            effective_state, node_id=node_id, node_type=normalized_type, node_config=node_config
        )
    if normalized_type == "ai.task":
        return _execute_ai_task_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "tool.query":
        return _execute_tool_mount_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "flow.condition":
        return _execute_condition_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "flow.delay":
        return _execute_delay_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "flow.wait_for_event":
        return _execute_wait_for_event_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "flow.poll":
        return _execute_poll_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "note":
        return _execute_note_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "approval.review":
        return _execute_approval_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type == "apply.action":
        return _execute_apply_action_node(effective_state, node_id=node_id, node_config=node_config)
    if normalized_type.startswith("operation."):
        return _execute_operation_node(
            effective_state, node_id=node_id, node_type=normalized_type, node_config=node_config
        )
    if normalized_type == "notification.webhook":
        return _execute_notification_webhook_node(effective_state, node_id=node_id, node_config=node_config)
    raise ValidationError(f"Unsupported workflow graph node type: {normalized_type}")


def _normalize_match_tokens(value: Any) -> set[str]:
    if isinstance(value, bool):
        return {"true", "1", "yes"} if value else {"false", "0", "no"}
    if value is None:
        return {""}
    normalized = str(value).strip()
    if not normalized:
        return {""}
    return {normalized, normalized.lower()}


def _route_value_for_node(
    state: WorkflowExecutionState, *, node_id: str, node_type: str, node_config: dict[str, Any]
) -> Any:
    outputs = dict(state.get("node_outputs") or {})
    payload = dict(outputs.get(node_id) or {})
    normalized_type = normalize_node_type(node_type)
    route_path = str(node_config.get("route_path") or "").strip()
    if route_path:
        route = _lookup_path(payload, route_path)
        if route is not None:
            return route
    if normalized_type == "flow.condition":
        return payload.get("result")
    if normalized_type == "approval.review":
        return dict(payload.get("decision") or {}).get("action") or "approve"
    if normalized_type == "flow.wait_for_event":
        return payload.get("status") or "matched"
    if normalized_type == "flow.poll":
        return payload.get("status") or "success"
    if normalized_type == "apply.action":
        return payload.get("status") or "success"
    if normalized_type.startswith("operation."):
        return payload.get("status") or "success"
    if normalized_type == "notification.webhook":
        return payload.get("status") or "done"
    if normalized_type == "ai.task":
        # New contract: route stored as __route__ by _split_ai_output
        return payload.get("__route__") or "default"
    return "default"


def _resolve_next_node(
    state: WorkflowExecutionState,
    *,
    node_id: str,
    node_type: str,
    node_config: dict[str, Any],
    outgoing_edges: list[dict[str, Any]],
) -> str:
    if not outgoing_edges:
        return "__finalize__"
    route_value = _route_value_for_node(state, node_id=node_id, node_type=node_type, node_config=node_config)
    route_tokens = _normalize_match_tokens(route_value)
    default_edge = None
    for edge in outgoing_edges:
        config = dict(edge.get("config") or {})
        match_value = (
            str(config.get("match") or "").strip()
            or str(edge.get("source_handle") or "").strip()
            or str(edge.get("label") or "").strip()
        )
        if not match_value:
            default_edge = default_edge or edge
            continue
        if match_value.lower() in route_tokens or match_value in route_tokens:
            return str(edge.get("target") or "__finalize__")
    if default_edge is not None:
        return str(default_edge.get("target") or "__finalize__")
    return str(outgoing_edges[0].get("target") or "__finalize__")


def _finalize_result_node(state: WorkflowExecutionState) -> WorkflowExecutionState:
    trace = _copy_trace(state)
    result_payload = dict(state.get("result_payload") or {})
    if not result_payload:
        result_payload = {
            "status": "completed",
            "applied": False,
            "action": dict(state.get("approval_result") or {}).get("action"),
        }
    result_payload["graph_execution"] = {
        "completed_nodes": [item.get("node_key") for item in trace],
        "completed_step_count": len(trace),
    }
    return {"result_payload": result_payload}


def _graph_nodes(graph_payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for item in graph_payload.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        node = dict(item)
        node["type"] = normalize_node_type(str(node.get("type") or "note"))
        nodes.append(node)
    return nodes


def _graph_edges(graph_payload: dict[str, Any]) -> list[dict[str, Any]]:
    graph_nodes = [dict(item) for item in graph_payload.get("nodes") or [] if isinstance(item, dict)]
    graph_edges = [dict(item) for item in graph_payload.get("edges") or [] if isinstance(item, dict)]
    return flow_edges(graph_nodes, graph_edges)


def _start_node_id(nodes: list[dict[str, Any]]) -> str:
    if not nodes:
        raise ValidationError("Workflow graph has no nodes")
    for node in nodes:
        if str(node.get("type") or "").startswith("trigger."):
            return str(node.get("id") or "")
    return str(nodes[0].get("id") or "")


def _outgoing_edges(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        source = str(edge.get("source") or "").strip()
        if not source:
            continue
        adjacency.setdefault(source, []).append(edge)
    return adjacency


def _build_runtime_graph(checkpointer: SqliteSaver, graph_payload: dict[str, Any]):
    nodes = _graph_nodes(graph_payload)
    edges = _graph_edges(graph_payload)
    start_node = _start_node_id(nodes)
    adjacency = _outgoing_edges(edges)
    nodes_by_id = {str(item.get("id") or ""): item for item in nodes if str(item.get("id") or "").strip()}

    builder = StateGraph(WorkflowExecutionState)

    for node_id, node in nodes_by_id.items():
        node_type = str(node.get("type") or "").strip()
        node_config = dict(node.get("config") or {})

        def make_executor(*, captured_node_id: str, captured_node_type: str, captured_node_config: dict[str, Any]):
            def executor(state: WorkflowExecutionState) -> WorkflowExecutionState:
                return _execute_graph_node(
                    state,
                    node_id=captured_node_id,
                    node_type=captured_node_type,
                    node_config=captured_node_config,
                )

            return executor

        builder.add_node(
            node_id,
            make_executor(captured_node_id=node_id, captured_node_type=node_type, captured_node_config=node_config),
        )

    builder.add_node("__finalize__", _finalize_result_node)
    builder.add_edge(START, start_node)

    for node_id, node in nodes_by_id.items():
        outgoing = adjacency.get(node_id, [])
        if not outgoing:
            builder.add_edge(node_id, "__finalize__")
            continue
        if len(outgoing) == 1:
            config = dict(outgoing[0].get("config") or {})
            if not str(
                config.get("match") or outgoing[0].get("label") or outgoing[0].get("source_handle") or ""
            ).strip():
                builder.add_edge(node_id, str(outgoing[0].get("target") or "__finalize__"))
                continue

        node_type = str(node.get("type") or "").strip()
        node_config = dict(node.get("config") or {})

        def make_router(
            *,
            captured_node_id: str,
            captured_node_type: str,
            captured_node_config: dict[str, Any],
            captured_outgoing: list[dict[str, Any]],
        ):
            def route(state: WorkflowExecutionState) -> str:
                return _resolve_next_node(
                    state,
                    node_id=captured_node_id,
                    node_type=captured_node_type,
                    node_config=captured_node_config,
                    outgoing_edges=captured_outgoing,
                )

            return route

        builder.add_conditional_edges(
            node_id,
            make_router(
                captured_node_id=node_id,
                captured_node_type=node_type,
                captured_node_config=node_config,
                captured_outgoing=outgoing,
            ),
        )

    builder.add_edge("__finalize__", END)
    return builder.compile(checkpointer=checkpointer)
