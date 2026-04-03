from __future__ import annotations

from typing import Any

from aerisun.domain.automation.compat import normalize_node_type
from aerisun.domain.automation.schemas import (
    AgentWorkflowCatalogNodeTypeRead,
    AgentWorkflowCatalogOperationRead,
)
from aerisun.domain.automation.tool_surface import get_action_surface, get_tool_surface, list_action_surfaces

EDGE_KIND_TRIGGER = "trigger"
EDGE_KIND_DATA = "data"
EDGE_KIND_TOOL = "tool"
EDGE_KIND_ACTION = "action"
EDGE_KIND_CONTROL = "control"
AI_TASK_MOUNT_PORT_IDS = {"mount_1", "mount_2", "mount_3", "mount_4"}


def _node_index(graph_nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("id") or "").strip(): dict(node)
        for node in graph_nodes
        if isinstance(node, dict) and str(node.get("id") or "").strip()
    }


def edge_kind(
    edge: dict[str, Any],
    *,
    nodes_by_id: dict[str, dict[str, Any]] | None = None,
) -> str:
    config = dict(edge.get("config") or {})
    explicit = str(config.get("kind") or "").strip().lower()
    if explicit in {EDGE_KIND_TRIGGER, EDGE_KIND_DATA, EDGE_KIND_TOOL, EDGE_KIND_ACTION, EDGE_KIND_CONTROL}:
        return explicit

    source_handle = str(edge.get("source_handle") or "").strip().lower()
    target_handle = str(edge.get("target_handle") or "").strip().lower()
    source_node_type = ""
    target_node_type = ""
    if nodes_by_id is not None:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        source_node_type = normalize_node_type(str(dict(nodes_by_id.get(source) or {}).get("type") or ""))
        target_node_type = normalize_node_type(str(dict(nodes_by_id.get(target) or {}).get("type") or ""))

    if source_node_type == "tool.query" and target_node_type == "ai.task" and target_handle in AI_TASK_MOUNT_PORT_IDS:
        return EDGE_KIND_TOOL
    if source_node_type == "apply.action" and target_node_type == "ai.task" and target_handle in AI_TASK_MOUNT_PORT_IDS:
        return EDGE_KIND_ACTION
    if (
        source_node_type.startswith("trigger.")
        and target_node_type == "ai.task"
        and target_handle in AI_TASK_MOUNT_PORT_IDS
    ):
        return EDGE_KIND_TRIGGER
    if (
        source_node_type == "approval.review"
        and target_node_type == "ai.task"
        and target_handle in AI_TASK_MOUNT_PORT_IDS
    ):
        return EDGE_KIND_CONTROL
    if (
        source_handle in {"approval", "approved", "rejected", "default", "route", "control"}
        or target_handle == "control"
    ):
        return EDGE_KIND_CONTROL
    if source_node_type.startswith("trigger.") or target_node_type.startswith("trigger."):
        return EDGE_KIND_TRIGGER
    return EDGE_KIND_DATA


def flow_edges(graph_nodes: list[dict[str, Any]], graph_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes_by_id = _node_index(graph_nodes)
    return [
        dict(edge)
        for edge in graph_edges
        if isinstance(edge, dict)
        and edge_kind(dict(edge), nodes_by_id=nodes_by_id) not in {EDGE_KIND_TOOL, EDGE_KIND_ACTION}
    ]


def reverse_flow_adjacency(
    graph_nodes: list[dict[str, Any]], graph_edges: list[dict[str, Any]]
) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {}
    for edge in flow_edges(graph_nodes, graph_edges):
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source and target:
            reverse.setdefault(target, []).append(source)
    return reverse


def mounted_tool_surface_keys(
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    *,
    ai_node_id: str,
) -> list[str]:
    nodes_by_id = _node_index(graph_nodes)
    tool_keys: list[str] = []
    for edge in graph_edges:
        if not isinstance(edge, dict):
            continue
        if edge_kind(dict(edge), nodes_by_id=nodes_by_id) != EDGE_KIND_TOOL:
            continue
        if str(edge.get("target") or "").strip() != ai_node_id:
            continue
        source_id = str(edge.get("source") or "").strip()
        source_node = dict(nodes_by_id.get(source_id) or {})
        if normalize_node_type(str(source_node.get("type") or "")) != "tool.query":
            continue
        node_config = dict(source_node.get("config") or {})
        surface_keys = node_config.get("surface_keys")
        if isinstance(surface_keys, list):
            for item in surface_keys:
                surface_key = str(item or "").strip()
                if surface_key:
                    tool_keys.append(surface_key)
            continue
        surface_key = str(node_config.get("surface_key") or "").strip()
        if surface_key:
            tool_keys.append(surface_key)
    return list(dict.fromkeys(tool_keys))


def mounted_action_surface_keys(
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    *,
    ai_node_id: str,
) -> list[str]:
    nodes_by_id = _node_index(graph_nodes)
    action_keys: list[str] = []
    for edge in graph_edges:
        if not isinstance(edge, dict):
            continue
        if edge_kind(dict(edge), nodes_by_id=nodes_by_id) != EDGE_KIND_ACTION:
            continue
        if str(edge.get("target") or "").strip() != ai_node_id:
            continue
        source_id = str(edge.get("source") or "").strip()
        source_node = dict(nodes_by_id.get(source_id) or {})
        if normalize_node_type(str(source_node.get("type") or "")) != "apply.action":
            continue
        surface_key = str(dict(source_node.get("config") or {}).get("surface_key") or "").strip()
        if surface_key:
            action_keys.append(surface_key)
    return list(dict.fromkeys(action_keys))


def mounted_tool_nodes(
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    *,
    ai_node_id: str,
) -> list[dict[str, Any]]:
    nodes_by_id = _node_index(graph_nodes)
    mounted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for edge in graph_edges:
        if not isinstance(edge, dict):
            continue
        if edge_kind(dict(edge), nodes_by_id=nodes_by_id) != EDGE_KIND_TOOL:
            continue
        if str(edge.get("target") or "").strip() != ai_node_id:
            continue
        source_id = str(edge.get("source") or "").strip()
        if not source_id or source_id in seen:
            continue
        node = dict(nodes_by_id.get(source_id) or {})
        if normalize_node_type(str(node.get("type") or "")) != "tool.query":
            continue
        mounted.append(node)
        seen.add(source_id)
    return mounted


def _outgoing_flow_edges(
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    *,
    node_id: str,
) -> list[dict[str, Any]]:
    return [edge for edge in flow_edges(graph_nodes, graph_edges) if str(edge.get("source") or "").strip() == node_id]


def route_edge_labels(
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    *,
    ai_node_id: str,
) -> list[str]:
    outgoing = _outgoing_flow_edges(graph_nodes, graph_edges, node_id=ai_node_id)
    preferred = [edge for edge in outgoing if str(edge.get("source_handle") or "").strip() == "route"]
    route_edges = preferred or outgoing
    labels: list[str] = []
    for edge in route_edges:
        config = dict(edge.get("config") or {})
        match_value = (
            str(config.get("match") or "").strip()
            or str(config.get("match_value") or "").strip()
            or str(edge.get("label") or "").strip()
        )
        if match_value:
            labels.append(match_value)
    return list(dict.fromkeys(labels))


def _find_operation(
    operation_catalog: list[AgentWorkflowCatalogOperationRead],
    operation_key: str,
) -> AgentWorkflowCatalogOperationRead | None:
    for item in operation_catalog:
        if item.key == operation_key:
            return item
    return None


def derive_ai_output_schema(
    *,
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    ai_node_id: str,
    operation_catalog: list[AgentWorkflowCatalogOperationRead],
    node_type_registry: dict[str, AgentWorkflowCatalogNodeTypeRead],
    workflow_key: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    nodes_by_id = _node_index(graph_nodes)
    downstream_edges = _outgoing_flow_edges(graph_nodes, graph_edges, node_id=ai_node_id)
    result_edges = [edge for edge in downstream_edges if str(edge.get("source_handle") or "").strip() != "route"]
    downstream_node_ids = {str(edge.get("target") or "").strip() for edge in result_edges}
    downstream_nodes = [dict(nodes_by_id[node_id]) for node_id in downstream_node_ids if node_id in nodes_by_id]

    properties: dict[str, Any] = {}
    required_fields: list[str] = []
    source_node_ids: list[str] = []

    for node in downstream_nodes:
        node_id = str(node.get("id") or "")
        node_type = normalize_node_type(str(node.get("type") or ""))
        config = dict(node.get("config") or {})

        if node_type.startswith("operation."):
            op_key = str(config.get("operation_key") or "").strip()
            op_def = _find_operation(operation_catalog, op_key)
            if op_def is not None:
                props = dict((op_def.input_schema or {}).get("properties") or {})
                required = set((op_def.input_schema or {}).get("required") or [])
                for name, schema in props.items():
                    if name.endswith("_id") or name == "id":
                        continue
                    if name not in properties:
                        properties[name] = dict(schema or {"type": "string"})
                    if name in required and name not in required_fields:
                        required_fields.append(name)
                source_node_ids.append(node_id)
            continue

        if node_type == "approval.review":
            properties.setdefault("summary", {"type": "string", "description": "AI analysis summary"})
            properties.setdefault(
                "needs_approval", {"type": "boolean", "description": "Whether human approval is needed"}
            )
            if "summary" not in required_fields:
                required_fields.append("summary")
            if "needs_approval" not in required_fields:
                required_fields.append("needs_approval")
            source_node_ids.append(node_id)
            continue

        if node_type == "apply.action":
            surface_key = str(config.get("surface_key") or "").strip()
            if surface_key:
                surface = next(
                    (item for item in list_action_surfaces(workflow_key) if item.key == surface_key),
                    None,
                )
                if surface is not None:
                    props = dict((surface.input_schema or {}).get("properties") or {})
                    required = set((surface.input_schema or {}).get("required") or [])
                    for name, schema in props.items():
                        if name not in properties:
                            properties[name] = dict(schema or {"type": "string"})
                        if name in required and name not in required_fields:
                            required_fields.append(name)
                    source_node_ids.append(node_id)
            continue

        if node_type == "flow.condition":
            expression = str(config.get("expression") or "").strip()
            for shortcut in ("summary", "action", "needs_approval"):
                if shortcut in expression and shortcut not in properties:
                    properties[shortcut] = {"type": "string" if shortcut != "needs_approval" else "boolean"}
            source_node_ids.append(node_id)
            continue

        type_def = node_type_registry.get(node_type)
        if type_def is None:
            continue
        for port in type_def.input_ports:
            data_schema = port.data_schema
            if not data_schema or not isinstance(data_schema, dict):
                continue
            for prop_name, prop_schema in dict(data_schema.get("properties") or {}).items():
                properties.setdefault(prop_name, dict(prop_schema))
        if properties:
            source_node_ids.append(node_id)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required_fields:
        schema["required"] = required_fields
    return schema, source_node_ids


def validate_tool_mount(
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    *,
    ai_node_id: str,
    workflow_key: str,
) -> list[str]:
    errors: list[str] = []
    for tool_key in mounted_tool_surface_keys(graph_nodes, graph_edges, ai_node_id=ai_node_id):
        try:
            surface = get_tool_surface(tool_key, workflow_key=workflow_key)
        except Exception:
            errors.append(f"Unknown tool surface: {tool_key!r}")
            continue
        if surface.kind != "query":
            errors.append(f"AI task may only mount readonly query tool surfaces. Invalid surface: {tool_key!r}.")
    return errors


def validate_action_mount(
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    *,
    ai_node_id: str,
    workflow_key: str,
) -> list[str]:
    errors: list[str] = []
    for action_key in mounted_action_surface_keys(graph_nodes, graph_edges, ai_node_id=ai_node_id):
        try:
            get_action_surface(action_key, workflow_key=workflow_key)
        except Exception:
            errors.append(f"Unknown action surface: {action_key!r}")
    return errors
