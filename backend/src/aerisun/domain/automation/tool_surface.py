from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.agent.capabilities.registry import (
    AgentCapabilityDefinition,
    execute_capability,
    list_capability_definitions,
)
from aerisun.domain.automation.packs import (
    compiled_surface_catalog_from_pack,
    load_workflow_pack,
    workflow_pack_exists,
)
from aerisun.domain.automation.schemas import (
    ActionSurfaceRead,
    ActionSurfaceSpec,
    QuerySurfaceSpec,
    ToolSurfaceRead,
)
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

ACTION_BUNDLE_ENTRY_SEPARATOR = "#"
QUERY_SURFACE_CAPABILITY_ALIASES = {
    "get_admin_content": "observe.content.admin_items.get",
    "list_admin_tags": "observe.content.tags.list",
    "list_comment_moderation_queue": "observe.moderation.comments.list",
}


def _query_surface_key_for_capability(capability_name: str) -> str:
    return QUERY_SURFACE_CAPABILITY_ALIASES.get(capability_name, capability_name)


def _query_surface_capability_name(key: str) -> str:
    for capability_name, alias in QUERY_SURFACE_CAPABILITY_ALIASES.items():
        if alias == key:
            return capability_name
    return key


# ---------------------------------------------------------------------------
# Adapter: capability → ToolSurfaceRead (query surface)
# ---------------------------------------------------------------------------


def capability_to_query_surface(cap: AgentCapabilityDefinition) -> ToolSurfaceRead:
    """Convert a read-intent capability into a ToolSurfaceRead."""
    properties = dict(cap.input_schema.get("properties") or {})
    return ToolSurfaceRead(
        key=_query_surface_key_for_capability(cap.name),
        base_capability=cap.name,
        kind="query",
        workflow_local=False,
        domain=cap.domain or "misc",
        sensitivity="business",
        label=cap.label or cap.resolved_label,
        description=cap.description,
        risk_level=cap.risk_level,
        required_scopes=list(cap.required_scopes),
        input_schema=dict(cap.input_schema),
        response_schema=dict(cap.output_schema),
        output_projection={},
        requires_approval=False,
        allowed_args=list(properties.keys()),
        fixed_args={},
        bound_args={},
        human_card={
            "reads": [f"读取：{cap.label or cap.resolved_label}。"],
            "cannot_read": ["不会执行写入、删除、恢复、审核或其他副作用。"],
            "can_act": ["这是只读查询工具，只会返回查询结果。"],
            "cannot_act": ["不能直接修改任何内容、配置、资源或系统状态。"],
            "parameter_sources": [
                f"可选参数：{', '.join(sorted(properties.keys()))}" if properties else "这个查询工具不需要额外参数。",
            ],
        },
    )


# ---------------------------------------------------------------------------
# Adapter: capability → ActionSurfaceRead (action surface)
# ---------------------------------------------------------------------------


def capability_to_action_surface(cap: AgentCapabilityDefinition) -> ActionSurfaceRead:
    """Convert a write/action-intent capability into an ActionSurfaceRead."""
    properties = dict(cap.input_schema.get("properties") or {})
    allowed_args = list(properties.keys())
    parameter_sources: list[str] = []
    if allowed_args:
        parameter_sources.append(f"允许输入：{', '.join(allowed_args)}")
    return ActionSurfaceRead(
        key=cap.name,
        action_key=cap.name,
        domain=cap.domain or "misc",
        base_capability=cap.name,
        kind="action",
        workflow_local=False,
        label=cap.label or cap.resolved_label,
        description=cap.description,
        risk_level=cap.risk_level,
        required_scopes=list(cap.required_scopes),
        fixed_args={},
        allowed_args=allowed_args,
        bound_args={},
        input_schema=dict(cap.input_schema),
        output_projection={},
        requires_approval=cap.requires_approval,
        requires_ref=False,
        allowed_source_query_keys=[],
        ref_binding={},
        human_card={
            "reads": [f"读取并执行：{cap.label or cap.resolved_label}。"],
            "cannot_read": ["不会泄露任何机密字段或内部 secret。"],
            "can_act": [f"执行动作：{cap.label or cap.resolved_label}。"],
            "cannot_act": ["不会执行未在这个动作定义里声明的副作用。"],
            "parameter_sources": parameter_sources,
        },
    )


def _resolve_path(obj: Any, path: str) -> Any:
    current = obj
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _has_bound_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _first_bound_value(*values: Any) -> Any:
    for value in values:
        if _has_bound_value(value):
            return value
    return None


def _common_surface_arg_value(
    arg_name: str,
    *,
    input_payload: dict[str, Any] | None,
    bound_values: dict[str, Any] | None,
) -> Any:
    normalized = str(arg_name or "").strip().lower()
    payload = dict(input_payload or {})
    values = dict(bound_values or {})
    input_data = dict(values.get("input") or {})
    agent_output = dict(values.get("agent_output") or {})
    approval = dict(values.get("approval") or {})
    state = dict(values.get("state") or {})

    mounted_trigger = dict(input_data.get("mounted_trigger") or {})
    context_payload = dict(input_data.get("context_payload") or mounted_trigger.get("context_payload") or {})
    trigger_inputs = dict(input_data.get("trigger_inputs") or mounted_trigger.get("inputs") or {})
    state_context_payload = dict(state.get("context_payload") or {})
    state_inputs = dict(state.get("inputs") or {})

    target_type = str(
        _first_bound_value(
            input_data.get("target_type"),
            mounted_trigger.get("target_type"),
            state.get("target_type"),
        )
        or ""
    ).strip()
    target_id = _first_bound_value(
        input_data.get("target_id"),
        mounted_trigger.get("target_id"),
        state.get("target_id"),
    )

    if normalized == "target_id":
        return target_id

    if normalized in {"item_id", "content_id"}:
        value = _first_bound_value(
            context_payload.get(normalized),
            context_payload.get("item_id"),
            context_payload.get("content_id"),
            trigger_inputs.get(normalized),
            trigger_inputs.get("item_id"),
            trigger_inputs.get("content_id"),
            state_context_payload.get(normalized),
            state_context_payload.get("item_id"),
            state_context_payload.get("content_id"),
            state_inputs.get(normalized),
            state_inputs.get("item_id"),
            state_inputs.get("content_id"),
            payload.get(normalized),
            payload.get("item_id"),
            payload.get("content_id"),
        )
        if value is not None:
            return value
        if target_type == "content":
            return target_id
        return None

    if normalized == "content_type":
        return _first_bound_value(
            context_payload.get("content_type"),
            trigger_inputs.get("content_type"),
            state_context_payload.get("content_type"),
            state_inputs.get("content_type"),
            payload.get("content_type"),
        )

    if normalized == "comment_id":
        value = _first_bound_value(
            context_payload.get("comment_id"),
            trigger_inputs.get("comment_id"),
            state_context_payload.get("comment_id"),
            state_inputs.get("comment_id"),
            payload.get("comment_id"),
        )
        if value is not None:
            return value
        if target_type == "comment":
            return target_id
        return None

    if normalized == "entry_id":
        value = _first_bound_value(
            context_payload.get("entry_id"),
            trigger_inputs.get("entry_id"),
            state_context_payload.get("entry_id"),
            state_inputs.get("entry_id"),
            payload.get("entry_id"),
        )
        if value is not None:
            return value
        if target_type == "guestbook":
            return target_id
        return None

    if normalized in {"slug", "content_slug"}:
        return _first_bound_value(
            context_payload.get(normalized),
            context_payload.get("slug"),
            context_payload.get("content_slug"),
            trigger_inputs.get(normalized),
            trigger_inputs.get("slug"),
            trigger_inputs.get("content_slug"),
            state_context_payload.get(normalized),
            state_context_payload.get("slug"),
            state_context_payload.get("content_slug"),
            state_inputs.get(normalized),
            state_inputs.get("slug"),
            state_inputs.get("content_slug"),
            payload.get(normalized),
            payload.get("slug"),
            payload.get("content_slug"),
        )

    if normalized == "action":
        return _first_bound_value(
            payload.get("action"),
            approval.get("action"),
            agent_output.get("action"),
            input_data.get("action"),
            state.get("action"),
        )

    if normalized == "reason":
        return _first_bound_value(
            payload.get("reason"),
            approval.get("reason"),
            agent_output.get("reason"),
            agent_output.get("summary"),
            payload.get("summary"),
        )

    return _first_bound_value(
        payload.get(normalized),
        context_payload.get(normalized),
        trigger_inputs.get(normalized),
        state_context_payload.get(normalized),
        state_inputs.get(normalized),
        input_data.get(normalized),
        mounted_trigger.get(normalized),
        approval.get(normalized),
        agent_output.get(normalized),
        state.get(normalized),
    )


def _autofill_common_surface_arguments(
    payload: dict[str, Any],
    *,
    arg_names: list[str],
    input_payload: dict[str, Any] | None,
    bound_values: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(payload or {})
    context_bound_arg_names = {
        "target_id",
        "item_id",
        "content_id",
        "content_type",
        "comment_id",
        "entry_id",
        "slug",
        "content_slug",
    }
    for arg_name in arg_names:
        if not str(arg_name or "").strip():
            continue
        normalized_arg_name = str(arg_name or "").strip().lower()
        if (
            normalized_arg_name not in context_bound_arg_names
            and arg_name in result
            and _has_bound_value(result.get(arg_name))
        ):
            continue
        resolved = _common_surface_arg_value(
            arg_name,
            input_payload=input_payload,
            bound_values=bound_values,
        )
        if _has_bound_value(resolved):
            result[arg_name] = resolved
    return result


def _normalize_content_type_value(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("content_type", "value", "type"):
            if key in value:
                return _normalize_content_type_value(value.get(key))
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
            return _normalize_content_type_value(parsed)
        return stripped
    return value


def _normalize_surface_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in dict(payload or {}).items():
        if str(key or "").strip().lower() == "content_type":
            normalized[key] = _normalize_content_type_value(value)
        else:
            normalized[key] = value
    return normalized


_PROJECTION_ALIASES: dict[str, str] = {
    "comment_id": "id",
    "entry_id": "id",
    "body_preview": "body",
}


def _projection_value(raw: dict[str, Any], key: str, schema: dict[str, Any]) -> Any:
    explicit_path = str(schema.get("path") or schema.get("source") or "").strip()
    if explicit_path:
        return _resolve_path(raw, explicit_path)
    if key in raw:
        return raw.get(key)
    alias_key = _PROJECTION_ALIASES.get(key)
    if alias_key:
        value = _resolve_path(raw, alias_key)
        if key == "body_preview" and isinstance(value, str):
            return value[:240]
        return value
    if key.endswith("_id") and "id" in raw:
        return raw.get("id")
    return None


def _project(raw: Any, projection: dict[str, Any]) -> Any:
    if not projection:
        return raw
    if isinstance(raw, list):
        return [_project(item, projection.get("items") or {}) for item in raw]
    if not isinstance(raw, dict):
        return raw
    properties = dict(projection.get("properties") or {})
    if not properties:
        return raw
    projected: dict[str, Any] = {}
    for key, schema in properties.items():
        if not isinstance(schema, dict):
            schema = {}
        value = _projection_value(raw, key, schema)
        if value is None:
            continue
        if isinstance(value, dict):
            projected[key] = _project(value, schema)
        elif isinstance(value, list):
            projected[key] = [_project(item, schema.get("items") or {}) for item in value]
        else:
            projected[key] = value
    return projected


def _surface_secret_path() -> Path:
    return get_settings().secrets_dir / "automation-surface-ref-secret.txt"


def _surface_secret() -> bytes:
    path = _surface_secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        seed = hashlib.sha256(f"{get_settings().app_name}:{get_settings().database_url}".encode()).hexdigest()
        path.write_text(seed, encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode("utf-8")


def _encode_surface_ref(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(_surface_secret(), body, hashlib.sha256).digest()
    body_token = base64.urlsafe_b64encode(body).decode("ascii")
    signature_token = base64.urlsafe_b64encode(signature).decode("ascii")
    return f"{body_token}.{signature_token}"


def decode_surface_ref(
    surface_ref: str,
    *,
    workflow_key: str,
    allowed_query_keys: list[str] | None = None,
) -> dict[str, Any]:
    try:
        if "." in surface_ref:
            body_token, signature_token = surface_ref.split(".", 1)
            body = base64.urlsafe_b64decode(body_token.encode("ascii"))
            signature = base64.urlsafe_b64decode(signature_token.encode("ascii"))
        else:
            raw = base64.urlsafe_b64decode(surface_ref.encode("ascii"))
            body, signature = raw.rsplit(b".", 1)
    except Exception as exc:  # pragma: no cover - defensive parser
        raise ValidationError("Invalid surface_ref encoding") from exc
    expected = hmac.new(_surface_secret(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValidationError("Invalid surface_ref signature")
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid surface_ref payload") from exc
    if str(payload.get("workflow_key") or "").strip() != workflow_key:
        raise ValidationError("surface_ref belongs to a different workflow")
    if allowed_query_keys and str(payload.get("query_surface_key") or "") not in set(allowed_query_keys):
        raise ValidationError("surface_ref source query is not allowed for this action")
    if not str(payload.get("resource_id") or "").strip():
        raise ValidationError("surface_ref does not contain a resource identifier")
    return payload


def _query_specs(workflow_key: str) -> dict[str, QuerySurfaceSpec]:
    if not workflow_key or not workflow_pack_exists(workflow_key):
        return {}
    pack = load_workflow_pack(workflow_key)
    return {item.key: item for item in pack.query_surfaces}


def _action_specs(workflow_key: str) -> dict[str, ActionSurfaceSpec]:
    if not workflow_key or not workflow_pack_exists(workflow_key):
        return {}
    pack = load_workflow_pack(workflow_key)
    return {item.key: item for item in pack.action_surfaces}


def _split_action_invocation_key(key: str) -> tuple[str, str | None]:
    raw = str(key or "").strip()
    if ACTION_BUNDLE_ENTRY_SEPARATOR not in raw:
        return raw, None
    surface_key, entry_key = raw.split(ACTION_BUNDLE_ENTRY_SEPARATOR, 1)
    return surface_key.strip(), entry_key.strip() or None


def _entry_as_action_surface(parent: ActionSurfaceRead, entry_key: str) -> ActionSurfaceRead | None:
    entry = next((item for item in parent.entries if item.key == entry_key), None)
    if entry is None:
        return None
    return ActionSurfaceRead(
        key=f"{parent.key}{ACTION_BUNDLE_ENTRY_SEPARATOR}{entry.key}",
        surface_mode="atomic",
        action_key=entry.action_key or parent.action_key,
        domain=parent.domain,
        base_capability=entry.base_capability or parent.base_capability,
        kind=parent.kind,
        workflow_local=parent.workflow_local,
        label=entry.label or parent.label,
        description=entry.description or parent.description,
        risk_level=entry.risk_level or parent.risk_level,
        required_scopes=list(entry.required_scopes or parent.required_scopes),
        fixed_args=dict(entry.fixed_args),
        allowed_args=list(entry.allowed_args),
        bound_args=dict(entry.bound_args),
        input_schema=dict(entry.input_schema),
        output_projection=dict(entry.output_projection),
        requires_approval=entry.requires_approval,
        requires_ref=entry.requires_ref,
        allowed_source_query_keys=list(entry.allowed_source_query_keys),
        ref_binding=dict(entry.ref_binding),
        human_card=dict(entry.human_card or parent.human_card),
        entries=[],
    )


def expand_action_surface_invocations(surface: ActionSurfaceRead) -> list[ActionSurfaceRead]:
    if surface.surface_mode != "bundle" or not surface.entries:
        return [surface]
    invocations: list[ActionSurfaceRead] = []
    for entry in surface.entries:
        invocation = _entry_as_action_surface(surface, entry.key)
        if invocation is not None:
            invocations.append(invocation)
    return invocations or [surface]


def _default_action_surfaces() -> list[ActionSurfaceRead]:
    surfaces: list[ActionSurfaceRead] = [
        capability_to_action_surface(cap)
        for cap in list_capability_definitions(kind="tool")
        if cap.intent in ("write", "action")
    ]
    surfaces.sort(key=lambda item: item.label or item.key)
    return surfaces


def list_tool_surfaces(workflow_key: str | None = None) -> list[ToolSurfaceRead]:
    merged: dict[str, ToolSurfaceRead] = {
        surface.key: surface
        for cap in list_capability_definitions(kind="tool")
        if cap.intent == "read"
        for surface in [capability_to_query_surface(cap)]
    }
    if workflow_key and workflow_pack_exists(workflow_key):
        compiled = compiled_surface_catalog_from_pack(load_workflow_pack(workflow_key))
        merged.update({item.key: item for item in compiled.query_surfaces})
    return sorted(merged.values(), key=lambda item: (item.domain or "misc", item.label or item.key, item.key))


def list_action_surfaces(workflow_key: str | None = None) -> list[ActionSurfaceRead]:
    merged: dict[str, ActionSurfaceRead] = {item.key: item for item in _default_action_surfaces()}
    if workflow_key and workflow_pack_exists(workflow_key):
        compiled = compiled_surface_catalog_from_pack(load_workflow_pack(workflow_key))
        merged.update({item.key: item for item in compiled.action_surfaces})
    return list(merged.values())


def get_tool_surface(key: str, *, workflow_key: str) -> ToolSurfaceRead:
    for surface in list_tool_surfaces(workflow_key):
        if surface.key == key:
            return surface
    raise ResourceNotFound(f"Unknown tool surface: {key}")


def get_action_surface(key: str, *, workflow_key: str) -> ActionSurfaceRead:
    for surface in list_action_surfaces(workflow_key):
        if surface.key == key:
            return surface
    raise ResourceNotFound(f"Unknown action surface: {key}")


def get_action_surface_invocation(key: str, *, workflow_key: str) -> ActionSurfaceRead:
    surface_key, entry_key = _split_action_invocation_key(key)
    surface = get_action_surface(surface_key, workflow_key=workflow_key)
    if entry_key is None:
        return surface
    invocation = _entry_as_action_surface(surface, entry_key)
    if invocation is None:
        raise ResourceNotFound(f"Unknown action surface entry: {key}")
    return invocation


def list_action_surface_invocations(
    workflow_key: str,
    *,
    surface_keys: list[str] | None = None,
) -> list[ActionSurfaceRead]:
    selected = set(surface_keys or [])
    surfaces = list_action_surfaces(workflow_key)
    if selected:
        surfaces = [surface for surface in surfaces if surface.key in selected]
    invocations: list[ActionSurfaceRead] = []
    for surface in surfaces:
        invocations.extend(expand_action_surface_invocations(surface))
    return invocations


def build_tool_surface_catalog(workflow_key: str) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in list_tool_surfaces(workflow_key)]


def build_action_surface_catalog(workflow_key: str) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in list_action_surfaces(workflow_key)]


def execute_tool_surface(
    session: Session,
    key: str,
    *,
    workflow_key: str,
    run_id: str,
    agent_args: dict[str, Any] | None = None,
    bound_values: dict[str, Any] | None = None,
) -> Any:
    spec = _query_specs(workflow_key).get(key)
    if spec is not None:
        merged: dict[str, Any] = dict(spec.fixed_args)
        for arg_name, binding in spec.bound_args.items():
            if binding.source == "literal":
                merged[arg_name] = binding.path
                continue
            if bound_values:
                resolved = _resolve_path(bound_values.get(binding.source, {}), binding.path)
                if resolved is not None:
                    merged[arg_name] = resolved

        if agent_args:
            for arg_name, value in agent_args.items():
                if arg_name in set(spec.allowed_args):
                    merged[arg_name] = value

        merged = _autofill_common_surface_arguments(
            merged,
            arg_names=list(spec.allowed_args or dict(spec.input_schema.get("properties") or {}).keys()),
            input_payload=dict(agent_args or {}),
            bound_values=bound_values,
        )
        merged = _normalize_surface_payload(merged)

        raw = execute_capability(session, kind="tool", name=spec.base_capability, **merged)
        projected = _project(raw, spec.output_projection) if spec.output_projection else raw
        if not spec.ref_id_field:
            return projected

        def attach_ref(item: dict[str, Any]) -> dict[str, Any]:
            resource_id = item.get(spec.ref_id_field)
            if resource_id is None:
                return item
            surface_ref = _encode_surface_ref(
                {
                    "workflow_key": workflow_key,
                    "run_id": run_id,
                    "query_surface_key": spec.key,
                    "resource": spec.ref_resource,
                    "resource_id": resource_id,
                    "allowed_action_keys": list(spec.allowed_action_keys),
                }
            )
            return {**item, "surface_ref": surface_ref}

        if isinstance(projected, dict):
            items = projected.get("items")
            if isinstance(items, list):
                projected = {
                    **projected,
                    "items": [attach_ref(item) if isinstance(item, dict) else item for item in items],
                }
            elif spec.ref_id_field in projected:
                projected = attach_ref(projected)
        return projected

    # Fallback: execute capability directly for read-intent tools not in a workflow pack.
    from aerisun.domain.agent.capabilities.registry import get_capability_definition

    try:
        cap = get_capability_definition(kind="tool", name=_query_surface_capability_name(key))
    except Exception:
        cap = None
    if cap is not None:
        payload = _autofill_common_surface_arguments(
            dict(agent_args or {}),
            arg_names=list(dict(cap.input_schema.get("properties") or {}).keys()),
            input_payload=dict(agent_args or {}),
            bound_values=bound_values,
        )
        payload = _normalize_surface_payload(payload)
        return execute_capability(session, kind="tool", name=cap.name, **payload)

    raise ResourceNotFound(f"Unknown tool surface: {key}")


def execute_action_surface(
    session: Session,
    key: str,
    *,
    workflow_key: str,
    run_id: str,
    input_payload: dict[str, Any] | None,
    bound_values: dict[str, Any] | None = None,
) -> Any:
    try:
        surface = get_action_surface_invocation(key, workflow_key=workflow_key)
    except ResourceNotFound as exc:
        raise ResourceNotFound(f"Unknown action surface: {key}") from exc
    if surface.surface_mode == "bundle":
        raise ValidationError(f"Action surface {surface.key} is a bundle. Choose one bundled action entry instead.")

    merged: dict[str, Any] = dict(surface.fixed_args)
    input_payload = dict(input_payload or {})

    requires_ref = bool(
        surface.requires_ref
        or list(surface.allowed_source_query_keys or [])
        or str(dict(surface.ref_binding or {}).get("resolve_to") or "").strip()
    )
    if requires_ref:
        ref_binding = dict(surface.ref_binding or {})
        ref_path = str(ref_binding.get("path") or "surface_ref")
        ref_source = str(ref_binding.get("source") or "input")
        if ref_source == "input":
            surface_ref = _resolve_path(input_payload, ref_path)
        else:
            surface_ref = _resolve_path((bound_values or {}).get(ref_source, {}), ref_path)
        if not isinstance(surface_ref, str) or not surface_ref.strip():
            raise ValidationError(f"Action surface {key} requires a surface_ref")
        ref_payload = decode_surface_ref(
            surface_ref,
            workflow_key=workflow_key,
            allowed_query_keys=list(surface.allowed_source_query_keys),
        )
        if ref_payload.get("run_id") != run_id:
            raise ValidationError("surface_ref belongs to a different run")
        resolve_to = str(ref_binding.get("resolve_to") or "target_id")
        merged[resolve_to] = ref_payload.get("resource_id")

    allowed_args = set(surface.allowed_args or [])
    if allowed_args:
        for arg_name in allowed_args:
            if arg_name in input_payload:
                merged[arg_name] = input_payload[arg_name]

    for arg_name, binding in dict(surface.bound_args or {}).items():
        binding_dict = dict(binding or {})
        binding_source = str(binding_dict.get("source") or "")
        binding_path = str(binding_dict.get("path") or "")
        if binding_source == "literal":
            merged[arg_name] = binding_path
            continue
        source_payload = input_payload if binding_source == "input" else (bound_values or {}).get(binding_source, {})
        resolved = _resolve_path(source_payload, binding_path)
        if resolved is not None:
            merged[arg_name] = resolved

    merged = _autofill_common_surface_arguments(
        merged,
        arg_names=list(surface.allowed_args or dict(surface.input_schema.get("properties") or {}).keys()),
        input_payload=input_payload,
        bound_values=bound_values,
    )
    merged = _normalize_surface_payload(merged)

    raw = execute_capability(session, kind="tool", name=surface.base_capability, **merged)
    return _project(raw, surface.output_projection) if surface.output_projection else raw
