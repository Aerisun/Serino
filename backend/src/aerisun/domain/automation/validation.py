from __future__ import annotations

from typing import Any

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_jsonschema
from sqlalchemy.orm import Session

from aerisun.domain.automation.catalog import build_workflow_catalog, derive_ai_output_schema
from aerisun.domain.automation.compat import normalize_node_type
from aerisun.domain.automation.compiler import (
    AI_TASK_MOUNT_PORT_IDS,
    EDGE_KIND_ACTION,
    EDGE_KIND_CONTROL,
    EDGE_KIND_DATA,
    EDGE_KIND_TOOL,
    EDGE_KIND_TRIGGER,
    edge_kind,
    flow_edges,
    mounted_action_surface_keys,
    mounted_tool_nodes,
    mounted_tool_surface_keys,
    reverse_flow_adjacency,
    route_edge_labels,
    validate_action_mount,
    validate_tool_mount,
)
from aerisun.domain.automation.operations import get_operation_definition
from aerisun.domain.automation.schemas import (
    AgentWorkflowCreate,
    AgentWorkflowRead,
    AgentWorkflowValidationIssueRead,
    AgentWorkflowValidationRead,
)
from aerisun.domain.automation.tool_surface import get_action_surface, get_tool_surface


def _catalog_node_schema_map(session: Session) -> dict[str, dict[str, Any]]:
    return {item.type: dict(item.config_schema or {}) for item in build_workflow_catalog(session).node_types}


def _graph_adjacency(graph: dict[str, Any]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    nodes = [dict(item) for item in graph.get("nodes") or [] if isinstance(item, dict)]
    edges = [dict(item) for item in graph.get("edges") or [] if isinstance(item, dict)]
    for edge in flow_edges(nodes, edges):
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target:
            continue
        adjacency.setdefault(source, []).append(target)
    return adjacency


def _has_cycle(graph: dict[str, Any]) -> bool:
    adjacency = _graph_adjacency(graph)
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in active:
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        active.add(node_id)
        for next_id in adjacency.get(node_id, []):
            if visit(next_id):
                return True
        active.remove(node_id)
        return False

    return any(visit(node_id) for node_id in adjacency)


def validate_workflow_definition(
    session: Session, workflow: AgentWorkflowRead | AgentWorkflowCreate | dict[str, Any]
) -> AgentWorkflowValidationRead:
    if isinstance(workflow, (AgentWorkflowRead, AgentWorkflowCreate)):
        payload = workflow.model_dump(mode="json")
    else:
        payload = dict(workflow)
    return compile_workflow(payload, session=session)


# ---------------------------------------------------------------------------
# compile_workflow — deep contract validation at save time
# ---------------------------------------------------------------------------


def _reverse_adjacency(graph: dict[str, Any]) -> dict[str, list[str]]:
    """Build target → [source, ...] map from edges."""
    nodes = [dict(item) for item in graph.get("nodes") or [] if isinstance(item, dict)]
    edges = [dict(item) for item in graph.get("edges") or [] if isinstance(item, dict)]
    return reverse_flow_adjacency(nodes, edges)


def _outgoing_edge_labels(graph: dict[str, Any], node_id: str) -> list[str]:
    """Collect labels / match_values from edges originating at *node_id*."""
    nodes = [dict(item) for item in graph.get("nodes") or [] if isinstance(item, dict)]
    edges = [dict(item) for item in graph.get("edges") or [] if isinstance(item, dict)]
    return route_edge_labels(nodes, edges, ai_node_id=node_id)


def compile_workflow(
    workflow: dict[str, Any],
    *,
    session: Session | None = None,
) -> AgentWorkflowValidationRead:
    """Validate the full workflow graph at save time.

    Checks input/tool/output contracts on ``ai.task`` nodes in addition to
    the general graph-structure rules (at-least-one-node, trigger presence,
    duplicate IDs, edge endpoints).
    """
    graph = dict(workflow.get("graph") or {})
    nodes = [dict(n) for n in graph.get("nodes") or [] if isinstance(n, dict)]
    edges = [dict(e) for e in graph.get("edges") or [] if isinstance(e, dict)]
    trigger_bindings = [dict(item) for item in workflow.get("trigger_bindings") or [] if isinstance(item, dict)]

    issues: list[AgentWorkflowValidationIssueRead] = []
    workflow_key = str(workflow.get("key") or "").strip()
    catalog = build_workflow_catalog(session, workflow_key=workflow_key) if session is not None else None
    node_type_registry = {item.type: item for item in (catalog.node_types if catalog else [])}
    operation_catalog = list(catalog.operation_catalog if catalog else [])
    node_ids = [str(n.get("id") or "").strip() for n in nodes if str(n.get("id") or "").strip()]
    node_id_set = set(node_ids)
    nodes_by_id = {str(n.get("id") or "").strip(): n for n in nodes if str(n.get("id") or "").strip()}
    reverse_adj = _reverse_adjacency(graph)
    has_trigger_node = any(str(n.get("type") or "").strip().startswith("trigger.") for n in nodes)
    has_webhook_trigger = any(normalize_node_type(str(n.get("type") or "").strip()) == "trigger.webhook" for n in nodes)
    has_approval = any(normalize_node_type(str(item.get("type") or "")) == "approval.review" for item in nodes)
    ai_output_port_usage: dict[tuple[str, str], int] = {}
    ai_mount_port_usage: dict[tuple[str, str], int] = {}
    schema_map = _catalog_node_schema_map(session) if session is not None else {}

    # ── General graph checks ──────────────────────────────────────────────

    if not nodes:
        issues.append(
            AgentWorkflowValidationIssueRead(
                code="graph.empty",
                message="Workflow graph must contain at least one node.",
            )
        )

    if len(node_id_set) != len(node_ids):
        issues.append(
            AgentWorkflowValidationIssueRead(
                code="graph.duplicate_id",
                message="Workflow graph contains duplicate node IDs.",
            )
        )

    if not has_trigger_node:
        issues.append(
            AgentWorkflowValidationIssueRead(
                code="graph.no_trigger",
                message="Workflow graph must contain at least one trigger node.",
            )
        )

    if not trigger_bindings:
        issues.append(
            AgentWorkflowValidationIssueRead(
                code="workflow.no_trigger_bindings",
                message="Workflow must declare at least one trigger binding.",
                path="trigger_bindings",
            )
        )

    if graph and _has_cycle(graph):
        issues.append(
            AgentWorkflowValidationIssueRead(
                code="graph.cycle_not_supported",
                message="Arbitrary graph cycles are not supported in workflow v2.",
                path="graph.edges",
            )
        )

    for edge in edges:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source not in node_id_set or target not in node_id_set:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.missing_edge_endpoint",
                    message=f"Edge references missing node (source={source!r}, target={target!r}).",
                    edge_id=str(edge.get("id") or ""),
                )
            )
            continue
        kind = edge_kind(edge, nodes_by_id=nodes_by_id)
        source_type = normalize_node_type(str((nodes_by_id.get(source) or {}).get("type") or ""))
        target_type = normalize_node_type(str((nodes_by_id.get(target) or {}).get("type") or ""))
        target_handle = str(edge.get("target_handle") or "").strip()
        target_definition = node_type_registry.get(target_type)
        target_input_ports = {
            str(port.id).strip()
            for port in (target_definition.input_ports if target_definition else [])
            if str(port.id).strip()
        }
        if kind == EDGE_KIND_TOOL and (source_type != "tool.query" or target_type != "ai.task"):
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_tool_edge",
                    message="Tool edges must connect tool.query -> ai.task.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_TOOL and target_handle not in AI_TASK_MOUNT_PORT_IDS:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_tool_mount_port",
                    message="Tool edges into ai.task must target one of the generic mount ports.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_ACTION and (source_type != "apply.action" or target_type != "ai.task"):
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_action_edge",
                    message="Action mount edges must connect apply.action -> ai.task.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_ACTION and target_handle not in AI_TASK_MOUNT_PORT_IDS:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_action_mount_port",
                    message="Action mount edges into ai.task must target one of the generic mount ports.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_TRIGGER and not source_type.startswith("trigger."):
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_trigger_edge",
                    message="Trigger edges must originate from a trigger node.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_TRIGGER and target_type == "ai.task" and target_handle not in AI_TASK_MOUNT_PORT_IDS:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_trigger_mount_port",
                    message="Trigger edges into ai.task must target one of the generic mount ports.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_CONTROL and source_type == "tool.query":
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_control_edge",
                    message="Tool nodes cannot emit control edges.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_CONTROL and source_type == "approval.review" and target_type == "ai.task":
            if target_handle not in AI_TASK_MOUNT_PORT_IDS:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="graph.invalid_approval_mount_port",
                        message="Approval edges into ai.task must target one of the generic mount ports.",
                        edge_id=str(edge.get("id") or ""),
                    )
                )
            elif target_definition is not None and not AI_TASK_MOUNT_PORT_IDS.intersection(target_input_ports):
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="graph.invalid_approval_mount_target",
                        message="Approval edges can only connect to AI nodes that expose generic mount ports.",
                        edge_id=str(edge.get("id") or ""),
                    )
                )
        if (
            kind == EDGE_KIND_CONTROL
            and source_type == "approval.review"
            and target_type != "ai.task"
            and target_handle == "mount_approval"
            and target_definition is not None
            and "mount_approval" not in target_input_ports
        ):
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_approval_mount_target",
                    message="Approval edges can only connect to nodes that expose a mount_approval input port.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_CONTROL and source_type != "approval.review" and target_handle in AI_TASK_MOUNT_PORT_IDS:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_approval_edge_source",
                    message="Only approval.review nodes can connect to ai.task mount ports as approval edges.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if (
            kind == EDGE_KIND_DATA
            and target_type == "ai.task"
            and target_handle not in {"input_1", "input_2", "input_3"}
        ):
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="graph.invalid_ai_input_port",
                    message="Data edges into ai.task must target input_1, input_2, or input_3.",
                    edge_id=str(edge.get("id") or ""),
                )
            )
        if kind == EDGE_KIND_DATA and source_type == "ai.task":
            source_handle = str(edge.get("source_handle") or "").strip()
            if source_handle not in {"output_1", "output_2"}:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="graph.invalid_ai_output_port",
                        message="Data edges from ai.task must originate from output_1 or output_2.",
                        edge_id=str(edge.get("id") or ""),
                    )
                )
            else:
                usage_key = (source, source_handle)
                ai_output_port_usage[usage_key] = ai_output_port_usage.get(usage_key, 0) + 1
                if ai_output_port_usage[usage_key] > 1:
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="graph.ai_output_port_occupied",
                            message=f"AI task output port {source_handle!r} on node {source!r} already has a downstream connection.",
                            edge_id=str(edge.get("id") or ""),
                        )
                    )
        if target_type == "ai.task" and target_handle in AI_TASK_MOUNT_PORT_IDS:
            usage_key = (target, target_handle)
            ai_mount_port_usage[usage_key] = ai_mount_port_usage.get(usage_key, 0) + 1
            if ai_mount_port_usage[usage_key] > 1:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="graph.ai_mount_port_occupied",
                        message=f"AI task mount port {target_handle!r} on node {target!r} already has a mounted connection.",
                        edge_id=str(edge.get("id") or ""),
                    )
                )

    for node in nodes:
        node_id = str(node.get("id") or "").strip()
        node_type = normalize_node_type(str(node.get("type") or "").strip())
        config = dict(node.get("config") or {})

        if session is not None:
            if node_type not in schema_map:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="graph.unsupported_node_type",
                        message=f"Unsupported node type: {node_type}",
                        path=f"graph.nodes.{node_id}.type",
                        node_id=node_id,
                    )
                )
                continue
            try:
                validate_jsonschema(instance=config, schema=schema_map[node_type])
            except JsonSchemaValidationError as exc:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="graph.invalid_node_config",
                        message=f"Invalid config for node {node_id}: {exc.message}",
                        path=f"graph.nodes.{node_id}.config",
                        node_id=node_id,
                    )
                )

        if node_type.startswith("operation."):
            operation_key = str(config.get("operation_key") or config.get("capability") or "").strip()
            try:
                get_operation_definition(operation_type=node_type.split(".", 1)[1], key=operation_key)
            except Exception:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="graph.unknown_operation",
                        message=f"Unknown operation key for node {node_id}: {operation_key}",
                        path=f"graph.nodes.{node_id}.config.operation_key",
                        node_id=node_id,
                    )
                )
            risk_level = str(config.get("risk_level") or "").strip().lower()
            if risk_level == "high" and not has_approval:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        level="warning",
                        code="workflow.high_risk_without_approval",
                        message=f"High-risk operation node {node_id!r} has no approval.review node anywhere in the graph.",
                        path=f"graph.nodes.{node_id}.config.risk_level",
                        node_id=node_id,
                    )
                )

        if node_type == "apply.action":
            surface_key = str(config.get("surface_key") or "").strip()
            if not surface_key:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="action.missing_surface_key",
                        message=f"Apply Action node {node_id!r} must declare a surface_key.",
                        node_id=node_id,
                    )
                )
            else:
                try:
                    surface = get_action_surface(surface_key, workflow_key=workflow_key)
                    is_action_mount_source = any(
                        edge_kind(edge, nodes_by_id=nodes_by_id) == EDGE_KIND_ACTION
                        and str(edge.get("source") or "").strip() == node_id
                        for edge in edges
                    )
                    if getattr(surface, "surface_mode", "atomic") == "bundle" and not is_action_mount_source:
                        issues.append(
                            AgentWorkflowValidationIssueRead(
                                code="action.bundle_requires_mount",
                                message=f"Bundle action surface {surface_key!r} must be mounted to an ai.task node, not executed directly as a standalone apply.action node.",
                                node_id=node_id,
                            )
                        )
                    if surface.requires_approval and not has_approval:
                        issues.append(
                            AgentWorkflowValidationIssueRead(
                                level="warning",
                                code="action.requires_approval",
                                message=f"Action surface {surface_key!r} recommends approval but the graph has no approval.review node.",
                                node_id=node_id,
                            )
                        )
                except Exception:
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="action.unknown_surface",
                            message=f"Action surface {surface_key!r} is not registered in this workflow pack.",
                            node_id=node_id,
                        )
                    )

        if node_type != "tool.query":
            continue
        surface_keys = config.get("surface_keys")
        selected_surface_keys: list[str] = []
        if isinstance(surface_keys, list):
            selected_surface_keys = [str(item or "").strip() for item in surface_keys if str(item or "").strip()]
        else:
            legacy_surface_key = str(config.get("surface_key") or "").strip()
            if legacy_surface_key:
                selected_surface_keys = [legacy_surface_key]
        if not selected_surface_keys:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="tool.missing_surface_keys",
                    message=f"Tool node {node_id!r} must declare at least one surface key.",
                    node_id=node_id,
                )
            )
            continue
        for surface_key in selected_surface_keys:
            try:
                surface = get_tool_surface(surface_key, workflow_key=workflow_key)
                if surface.kind != "query":
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="tool.non_readonly_surface",
                            message=f"Tool node {node_id!r} may only mount readonly query tool surfaces. Invalid surface: {surface_key!r}.",
                            node_id=node_id,
                        )
                    )
            except Exception:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="tool.unknown_surface",
                        message=f"Tool surface {surface_key!r} is not registered.",
                        node_id=node_id,
                    )
                )

    # ── Per-node contract checks for ai.task nodes ────────────────────────

    for node in nodes:
        node_id = str(node.get("id") or "").strip()
        node_type = normalize_node_type(str(node.get("type") or "").strip())
        if node_type != "ai.task":
            continue

        config = dict(node.get("config") or {})
        input_contract = dict(config.get("input_contract") or {})
        output_contract = dict(config.get("output_contract") or {})
        incoming_sources = set(reverse_adj.get(node_id, []))
        incoming_data_sources = {
            str(edge.get("source") or "").strip()
            for edge in edges
            if str(edge.get("target") or "").strip() == node_id
            and edge_kind(edge, nodes_by_id=nodes_by_id) in {EDGE_KIND_TRIGGER, EDGE_KIND_DATA}
        }
        upstream_types = {
            upstream_id: normalize_node_type(str((nodes_by_id.get(upstream_id) or {}).get("type") or "").strip())
            for upstream_id in incoming_sources
        }

        # ── 1. Input chain ────────────────────────────────────────────────

        for field_def in input_contract.get("fields") or []:
            if not isinstance(field_def, dict):
                continue
            selector = dict(field_def.get("selector") or {})
            source_type = str(selector.get("source") or "").strip()
            field_key = str(field_def.get("key") or "")

            if source_type == "node_output":
                upstream_id = str(selector.get("node_id") or "").strip()
                if upstream_id not in node_id_set:
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="input.missing_upstream",
                            message=f"Input field {field_key!r} references non-existent node {upstream_id!r}.",
                            node_id=node_id,
                        )
                    )
                elif upstream_id not in incoming_data_sources:
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="input.no_edge",
                            message=f"Input field {field_key!r} references node {upstream_id!r} but no edge connects it to this node.",
                            node_id=node_id,
                        )
                    )

            elif source_type == "trigger":
                if not any(upstream_type.startswith("trigger.") for upstream_type in upstream_types.values()):
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="input.no_trigger_edge",
                            message=f"Input field {field_key!r} uses trigger source but this AI node has no connected trigger upstream.",
                            node_id=node_id,
                        )
                    )

            elif source_type == "webhook":
                if not has_webhook_trigger or not any(
                    upstream_type == "trigger.webhook" for upstream_type in upstream_types.values()
                ):
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="input.no_webhook_edge",
                            message=f"Input field {field_key!r} uses webhook source but this AI node has no connected webhook trigger upstream.",
                            node_id=node_id,
                        )
                    )

            elif source_type == "literal":
                if selector.get("value") is None:
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            code="input.missing_upstream",
                            message=f"Input field {field_key!r} is a literal selector with no value.",
                            node_id=node_id,
                        )
                    )

        # ── 2. Tool chain ─────────────────────────────────────────────────

        mounted_tool_keys = mounted_tool_surface_keys(nodes, edges, ai_node_id=node_id)
        mounted_tool_node_ids = {
            str(item.get("id") or "") for item in mounted_tool_nodes(nodes, edges, ai_node_id=node_id)
        }
        tool_errors = validate_tool_mount(nodes, edges, ai_node_id=node_id, workflow_key=workflow_key)
        for message in tool_errors:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="tool.mount_invalid",
                    message=message,
                    node_id=node_id,
                )
            )
        action_errors = validate_action_mount(nodes, edges, ai_node_id=node_id, workflow_key=workflow_key)
        for message in action_errors:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="action.mount_invalid",
                    message=message,
                    node_id=node_id,
                )
            )
        for upstream_id in mounted_tool_node_ids:
            if upstream_id in incoming_sources:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        level="warning",
                        code="tool.mount_uses_flow_edge",
                        message=f"Tool node {upstream_id!r} is mounted to AI node {node_id!r}; it should not also participate in flow dependencies.",
                        node_id=node_id,
                    )
                )
        for tool_key in mounted_tool_keys:
            if not tool_key:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="tool.mount_missing_surface",
                        message=f"AI node {node_id!r} has a mounted tool edge without a valid surface key.",
                        node_id=node_id,
                    )
                )
        for action_key in mounted_action_surface_keys(nodes, edges, ai_node_id=node_id):
            if not action_key:
                issues.append(
                    AgentWorkflowValidationIssueRead(
                        code="action.mount_missing_surface",
                        message=f"AI node {node_id!r} has a mounted action edge without a valid surface key.",
                        node_id=node_id,
                    )
                )
        tool_usage_mode = str(config.get("tool_usage_mode") or "recommended").strip().lower()
        minimum_tool_calls = max(1, int(config.get("minimum_tool_calls") or 1))
        if tool_usage_mode == "required" and not (
            mounted_tool_keys or mounted_action_surface_keys(nodes, edges, ai_node_id=node_id)
        ):
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="tool.policy_requires_mount",
                    message=f"AI node {node_id!r} requires mounted capability usage, but no readonly tools or mounted actions are connected.",
                    node_id=node_id,
                )
            )
        if tool_usage_mode not in {"optional", "recommended", "required"}:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="tool.policy_invalid_mode",
                    message=f"AI node {node_id!r} has unsupported tool_usage_mode={tool_usage_mode!r}.",
                    node_id=node_id,
                )
            )
        if minimum_tool_calls < 1:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="tool.policy_invalid_minimum",
                    message=f"AI node {node_id!r} must declare minimum_tool_calls >= 1.",
                    node_id=node_id,
                )
            )

        # ── 3. Output chain ───────────────────────────────────────────────

        output_schema = (
            output_contract.get("output_schema")
            or output_contract.get("schema")
            or output_contract.get("schema_def")
            or {}
        )
        if not output_schema:
            derived_schema, _ = derive_ai_output_schema(
                graph_nodes=nodes,
                graph_edges=edges,
                ai_node_id=node_id,
                operation_catalog=operation_catalog,
                node_type_registry=node_type_registry,
                workflow_key=workflow_key,
            )
            output_schema = derived_schema or {}
        if not output_schema:
            output_schema = {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                },
            }
        route = dict(output_contract.get("route") or {})
        if (not output_schema or "type" not in output_schema) and isinstance(config, dict):
            legacy_schema = dict(config.get("output_schema") or {})
            if legacy_schema.get("type"):
                output_schema = legacy_schema
            elif str(config.get("route_path") or "").strip():
                output_schema = {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        str(config.get("route_path")): {"type": "string"},
                    },
                }
            elif _outgoing_edge_labels(graph, node_id):
                output_schema = {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "route": {"type": "string"},
                    },
                }
        if not route and isinstance(config, dict):
            legacy_route_field = str(config.get("route_path") or "").strip()
            if legacy_route_field:
                route = {"field": legacy_route_field, "enum": [], "enum_from_edges": False}

        if not output_schema or not isinstance(output_schema, dict) or "type" not in output_schema:
            issues.append(
                AgentWorkflowValidationIssueRead(
                    code="output.missing_schema",
                    message="Output contract must include a valid JSON Schema with a 'type' key.",
                    node_id=node_id,
                )
            )

        if route:
            edge_labels = _outgoing_edge_labels(graph, node_id)
            if route.get("enum_from_edges"):
                route["enum"] = edge_labels
            route_enum = set(route.get("enum") or [])
            if route_enum:
                uncovered = [lbl for lbl in edge_labels if lbl not in route_enum]
                if uncovered:
                    issues.append(
                        AgentWorkflowValidationIssueRead(
                            level="warning",
                            code="output.route_mismatch",
                            message=f"Outgoing edge labels {uncovered!r} are not covered by route enum.",
                            node_id=node_id,
                        )
                    )

    return AgentWorkflowValidationRead(
        ok=not any(issue.level == "error" for issue in issues),
        issues=issues,
    )
