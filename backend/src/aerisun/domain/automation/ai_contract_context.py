from __future__ import annotations

from typing import Any

from aerisun.domain.automation.catalog import workflow_node_type_registry
from aerisun.domain.automation.compat import normalize_node_type
from aerisun.domain.automation.compiler import (
    EDGE_KIND_CONTROL,
    EDGE_KIND_DATA,
    EDGE_KIND_TRIGGER,
    edge_kind,
    mounted_action_surface_keys,
    mounted_tool_surface_keys,
)
from aerisun.domain.automation.operations import list_operation_definitions
from aerisun.domain.automation.tool_surface import (
    get_tool_surface,
    list_action_surface_invocations,
    list_action_surfaces,
)


def _node_index(graph_nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("id") or "").strip(): dict(node)
        for node in graph_nodes
        if isinstance(node, dict) and str(node.get("id") or "").strip()
    }


def _schema_field_names(schema: dict[str, Any] | None) -> list[str]:
    if not isinstance(schema, dict):
        return []
    properties = dict(schema.get("properties") or {})
    return [str(name) for name in properties if str(name).strip()]


def _source_summary(source_type: str, source_config: dict[str, Any]) -> str:
    if source_type == "trigger.event":
        return str(source_config.get("event_type") or "").strip() or ", ".join(
            str(item).strip() for item in source_config.get("matched_events") or [] if str(item).strip()
        )
    if source_type == "trigger.webhook":
        return str(source_config.get("path") or "").strip()
    if source_type == "trigger.schedule":
        cron = str(source_config.get("cron") or "").strip()
        if cron:
            return cron
        interval_seconds = source_config.get("interval_seconds")
        if interval_seconds:
            return f"every {interval_seconds}s"
    return ""


def _slot_label(slot: str) -> str:
    normalized = str(slot or "").strip()
    if normalized.startswith("input_"):
        return f"Input {normalized.split('_')[-1]}"
    if normalized.startswith("mount_"):
        return f"Mount {normalized.split('_')[-1]}"
    return normalized or "Input"


def _port_definition(
    *,
    node_type: str,
    port_id: str,
    registry: dict[str, Any],
    direction: str,
) -> dict[str, Any] | None:
    node_def = registry.get(node_type)
    if node_def is None:
        return None
    ports = node_def.output_ports if direction == "output" else node_def.input_ports
    for port in ports:
        if str(port.id).strip() == port_id:
            return {
                "id": str(port.id),
                "label": str(port.label or port.id),
                "schema": dict(port.data_schema or {}) if getattr(port, "data_schema", None) else {},
            }
    return None


def _describe_upstream_usage(source_type: str, source_label: str) -> str:
    if source_type == "ai.task":
        return "This is the structured output from an upstream AI node."
    if source_type == "approval.review":
        return "This is the decision payload returned by a human approval node."
    if source_type == "apply.action":
        return "This is the execution result returned by an action node."
    if source_type == "notification.webhook":
        return "This is the delivery result produced by a webhook notification node."
    if source_type == "flow.condition":
        return "This is the branch result produced by a condition node."
    if source_type == "flow.delay":
        return "This is the resumed state produced by a delay node."
    if source_type == "flow.poll":
        return "This is the latest polling result and status."
    if source_type == "flow.wait_for_event":
        return "This is the event payload returned when a wait-for-event node resumes."
    if source_type.startswith("trigger."):
        return "This payload originates from the workflow trigger context."
    return f"This is structured data from upstream node {source_label}."


def _describe_downstream_usage(target_type: str, target_label: str) -> str:
    if target_type == "ai.task":
        return f"The next AI node {target_label} will receive this output as structured upstream context."
    if target_type == "apply.action":
        return f"Action node {target_label} will consume this output and execute a platform action."
    if target_type == "notification.webhook":
        return f"Webhook node {target_label} will use this output as notification payload/template context."
    if target_type == "approval.review":
        return f"Approval node {target_label} will use this output as review content."
    if target_type == "flow.condition":
        return f"Condition node {target_label} will branch based on fields from this output."
    if target_type == "flow.delay":
        return f"Delay node {target_label} will carry this output forward after waiting."
    if target_type == "flow.wait_for_event":
        return f"Wait-for-event node {target_label} will retain this output until continuation conditions are met."
    if target_type == "flow.poll":
        return f"Polling node {target_label} will continue checking status with this output."
    return f"Downstream node {target_label} will consume this output."


def build_ai_contract_context(
    *,
    workflow_key: str,
    workflow_config: dict[str, Any],
    ai_node_id: str,
    node_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph = dict(workflow_config.get("graph") or {})
    graph_nodes = [dict(item) for item in graph.get("nodes") or [] if isinstance(item, dict)]
    graph_edges = [dict(item) for item in graph.get("edges") or [] if isinstance(item, dict)]
    nodes_by_id = _node_index(graph_nodes)
    registry = workflow_node_type_registry()
    tool_keys = mounted_tool_surface_keys(
        graph_nodes,
        graph_edges,
        ai_node_id=ai_node_id,
    )
    action_keys = mounted_action_surface_keys(
        graph_nodes,
        graph_edges,
        ai_node_id=ai_node_id,
    )
    node_config = dict(node_config or {})

    upstream_inputs: list[dict[str, Any]] = []
    for edge in graph_edges:
        if str(edge.get("target") or "").strip() != ai_node_id:
            continue
        kind = edge_kind(edge, nodes_by_id=nodes_by_id)
        source_id = str(edge.get("source") or "").strip()
        source_node = dict(nodes_by_id.get(source_id) or {})
        source_type = normalize_node_type(str(source_node.get("type") or ""))
        source_label = str(source_node.get("label") or source_id)
        source_config = dict(source_node.get("config") or {})
        target_handle = str(edge.get("target_handle") or "").strip()
        source_handle = str(edge.get("source_handle") or "").strip()
        source_port = _port_definition(
            node_type=source_type,
            port_id=source_handle or "out",
            registry=registry,
            direction="output",
        )
        source_summary = _source_summary(source_type, source_config)
        entry = {
            "kind": kind,
            "slot": target_handle,
            "label": _slot_label(target_handle),
            "from_node_id": source_id,
            "from_node_type": source_type,
            "from_node_label": source_label,
            "source": {
                "node_label": source_label,
                "node_type": source_type,
            },
            "from_port": {
                "id": source_port["id"] if source_port else source_handle,
                "label": source_port["label"] if source_port else source_handle,
            },
            "provided_fields": _schema_field_names(source_port["schema"] if source_port else {}),
            "usage_note": _describe_upstream_usage(source_type, source_label),
            "source_summary": source_summary,
            "slot_note": str(
                dict(dict(node_config.get("input_slots") or {}).get(target_handle) or {}).get("note") or ""
            ).strip(),
            "note": {
                "title": "How to interpret this input",
                "summary": _describe_upstream_usage(source_type, source_label),
                "operator_note": str(
                    dict(dict(node_config.get("input_slots") or {}).get(target_handle) or {}).get("note") or ""
                ).strip(),
            },
        }
        if kind == EDGE_KIND_DATA:
            upstream_inputs.append(entry)
        elif kind == EDGE_KIND_TRIGGER:
            upstream_inputs.append(
                {
                    **entry,
                    "usage_note": "This trigger mount tells the AI under which trigger context it is currently running.",
                    "note": {
                        "title": "Trigger context",
                        "summary": "This mount tells the AI why it is currently running.",
                        "operator_note": "",
                    },
                }
            )
        elif kind == EDGE_KIND_CONTROL:
            upstream_inputs.append(
                {
                    **entry,
                    "usage_note": "This approval mount tells the AI whether human approval already happened and what the decision was.",
                    "note": {
                        "title": "Approval context",
                        "summary": "This mount tells the AI whether approval already happened and what the decision was.",
                        "operator_note": "",
                    },
                }
            )

    downstream_consumers: list[dict[str, Any]] = []
    operation_catalog = list_operation_definitions()
    for edge in graph_edges:
        if str(edge.get("source") or "").strip() != ai_node_id:
            continue
        if str(edge.get("source_handle") or "").strip() == "route":
            continue
        target_id = str(edge.get("target") or "").strip()
        target_node = dict(nodes_by_id.get(target_id) or {})
        target_type = normalize_node_type(str(target_node.get("type") or ""))
        target_label = str(target_node.get("label") or target_id)
        target_handle = str(edge.get("target_handle") or "").strip()
        target_port = _port_definition(
            node_type=target_type,
            port_id=target_handle or "in",
            registry=registry,
            direction="input",
        )
        required_fields: list[str] = _schema_field_names(target_port["schema"] if target_port else {})
        usage_note = _describe_downstream_usage(target_type, target_label)
        surface_key = ""
        surface_label = ""
        surface_description = ""
        surface_hints: list[str] = []
        format_requirements = ""
        if target_type.startswith("operation."):
            operation_key = str(dict(target_node.get("config") or {}).get("operation_key") or "").strip()
            op_def = next((item for item in operation_catalog if item.key == operation_key), None)
            if op_def is not None:
                required_fields = _schema_field_names(dict(op_def.input_schema or {}))
                surface_key = operation_key
                surface_label = str(op_def.label or operation_key).strip()
                surface_description = str(op_def.description or "").strip()
                surface_hints = [f"它会执行“{surface_label}”这件事。"] if surface_label else []
                usage_note = f"Operation node {target_label} will execute with fields taken from this AI output."
        elif target_type == "apply.action":
            surface_key = str(dict(target_node.get("config") or {}).get("surface_key") or "").strip()
            if surface_key:
                surface = next(
                    (item for item in list_action_surfaces(workflow_key) if item.key == surface_key),
                    None,
                )
                if surface is not None:
                    required_fields = _schema_field_names(dict(surface.input_schema or {}))
                    surface_label = str(surface.label or surface.key).strip()
                    surface_description = str(surface.description or "").strip()
                    surface_hints = [
                        str(item).strip()
                        for item in dict(surface.human_card or {}).get("can_act") or []
                        if str(item).strip()
                    ][:3]
                    usage_note = f"Action node {target_label} will pass this AI output into action surface {surface_label or surface.key}."
        elif target_type == "notification.webhook":
            format_requirements = str(dict(target_node.get("config") or {}).get("format_requirements") or "").strip()
        elif target_type == "approval.review" and not required_fields:
            required_fields = ["summary", "needs_approval"]
        downstream_consumers.append(
            {
                "target_node_id": target_id,
                "target_node_type": target_type,
                "target_node_label": target_label,
                "target": {
                    "node_label": target_label,
                    "node_type": target_type,
                },
                "target_port": {
                    "id": target_port["id"] if target_port else target_handle,
                    "label": target_port["label"] if target_port else target_handle,
                },
                "required_fields": required_fields,
                "usage_note": usage_note,
                "requirement_note": (
                    f"Required fields: {', '.join(required_fields)}"
                    if required_fields
                    else "No explicit field requirement was declared."
                ),
                "surface_key": surface_key,
                "surface_label": surface_label,
                "surface_description": surface_description,
                "surface_hints": surface_hints,
                "format_requirements": format_requirements,
                "note": {
                    "title": "How downstream will use this output",
                    "summary": usage_note,
                    "requirement": (
                        f"Required fields: {', '.join(required_fields)}"
                        if required_fields
                        else "No explicit field requirement was declared."
                    ),
                    "tips": [
                        *surface_hints,
                        *([format_requirements] if format_requirements else []),
                    ],
                },
            }
        )

    mounted_tools: list[dict[str, Any]] = []
    for tool_key in tool_keys:
        try:
            surface = get_tool_surface(tool_key, workflow_key=workflow_key)
        except Exception:
            continue
        # Attempt to enrich summary with ai_usage_hint from the capability registry.
        summary = surface.description
        try:
            from aerisun.domain.agent.capabilities.registry import get_capability_definition

            cap = get_capability_definition(kind="tool", name=surface.base_capability or surface.key)
            if cap.ai_usage_hint:
                summary = cap.ai_usage_hint
        except Exception:
            pass
        mounted_tools.append(
            {
                "key": surface.key,
                "label": surface.label,
                "description": surface.description,
                "domain": getattr(surface, "domain", ""),
                "sensitivity": getattr(surface, "sensitivity", ""),
                "parameters_schema": dict(surface.input_schema or {}),
                "allowed_arguments": list(surface.allowed_args or []),
                "fixed_arguments": dict(surface.fixed_args or {}),
                "auto_bound_arguments": sorted(dict(surface.bound_args or {}).keys()),
                "usage_notes": dict(surface.human_card or {}),
                "note": {
                    "title": "What this tool can help with",
                    "summary": summary,
                    "tips": [item for values in dict(surface.human_card or {}).values() for item in values][:4],
                },
            }
        )

    mounted_actions: list[dict[str, Any]] = []
    for surface in list_action_surface_invocations(workflow_key, surface_keys=action_keys):
        summary = surface.description
        try:
            from aerisun.domain.agent.capabilities.registry import get_capability_definition

            cap = get_capability_definition(kind="tool", name=surface.base_capability or surface.key.split("#", 1)[0])
            if cap.ai_usage_hint:
                summary = cap.ai_usage_hint
        except Exception:
            pass
        mounted_actions.append(
            {
                "key": surface.key,
                "surface_key": surface.key.split("#", 1)[0],
                "entry_key": surface.key.split("#", 1)[1] if "#" in surface.key else "",
                "label": surface.label,
                "description": surface.description,
                "domain": getattr(surface, "domain", ""),
                "risk_level": getattr(surface, "risk_level", "medium"),
                "parameters_schema": dict(surface.input_schema or {}),
                "allowed_arguments": list(surface.allowed_args or []),
                "fixed_arguments": dict(surface.fixed_args or {}),
                "auto_bound_arguments": sorted(dict(surface.bound_args or {}).keys()),
                "usage_notes": dict(surface.human_card or {}),
                "note": {
                    "title": "What this action can do",
                    "summary": summary,
                    "tips": [item for values in dict(surface.human_card or {}).values() for item in values][:4],
                },
            }
        )

    tool_usage_mode = str(node_config.get("tool_usage_mode") or "recommended").strip().lower() or "recommended"
    minimum_tool_calls = max(1, min(int(node_config.get("minimum_tool_calls") or 1), 10))

    return {
        "node_id": ai_node_id,
        "node_type": "ai.task",
        "upstream_inputs": upstream_inputs,
        "downstream_consumers": downstream_consumers,
        "mounted_tools": mounted_tools,
        "mounted_actions": mounted_actions,
        "tool_usage_policy": {
            "mode": tool_usage_mode,
            "minimum_tool_calls": minimum_tool_calls,
        },
        "output_contract": {
            "summary": ("This AI node should prepare a structured result for the connected downstream nodes."),
            "field_keys": sorted(
                {
                    field
                    for consumer in downstream_consumers
                    for field in consumer.get("required_fields") or []
                    if str(field).strip()
                }
            ),
        },
    }
