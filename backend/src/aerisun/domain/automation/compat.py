"""V1-to-V2 workflow migration and graph normalization helpers.

TODO: Plan removal once all persisted workflow data has been migrated to schema_version >= 2.
      Currently actively used by settings, packs, validation, runtime, compiler, and ai_contract_context.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aerisun.domain.automation.schemas import (
    AgentWorkflowGraph,
    AgentWorkflowRuntimePolicy,
    AgentWorkflowSummaryRead,
    AgentWorkflowTriggerBinding,
)

LEGACY_NODE_TYPE_ALIASES = {
    "trigger": "trigger.event",
    "ai_task": "ai.task",
    "approval_gate": "approval.review",
    "action": "operation.capability",
    "webhook": "notification.webhook",
    "condition": "flow.condition",
}

LEGACY_TRIGGER_TYPE_ALIASES = {
    "event": "trigger.event",
    "webhook": "trigger.webhook",
    "manual": "trigger.manual",
    "schedule": "trigger.schedule",
}


def normalize_node_type(value: str) -> str:
    normalized = (value or "").strip()
    return LEGACY_NODE_TYPE_ALIASES.get(normalized, normalized)


def normalize_binding_type(value: str) -> str:
    normalized = (value or "").strip()
    return LEGACY_TRIGGER_TYPE_ALIASES.get(normalized, normalized)


def migrate_ai_node_config(config: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy ai.task config to three-contract format."""
    # Already migrated?
    if "input_contract" in config:
        return deepcopy(config)

    new_config: dict[str, Any] = deepcopy(config)
    new_config.setdefault("instructions", config.get("instructions", ""))

    # --- Input contract ---
    input_fields: list[dict[str, Any]] = []
    input_mode = config.get("input_mode", "context_only")
    if input_mode in ("context_only", "context_and_outputs"):
        # Old mode: feed full context_payload -> single trigger field
        input_fields.append(
            {
                "key": "context",
                "field_schema": {"type": "object"},
                "required": True,
                "selector": {"source": "trigger", "path": ""},
            }
        )
    elif input_mode == "expression" and config.get("input_mappings"):
        for mapping in config["input_mappings"]:
            input_fields.append(
                {
                    "key": mapping.get("field_name", mapping.get("name", "")),
                    "field_schema": {"type": "string"},
                    "required": True,
                    "selector": {"source": "trigger", "path": mapping.get("expression", "")},
                }
            )
    new_config["input_contract"] = {"fields": input_fields}

    # --- Tool contract (empty for legacy) ---
    new_config.setdefault("tool_contract", {"tools": []})

    # --- Output contract ---
    output_mode = config.get("output_mode", "route")
    output_schema_props: dict[str, Any] = {"summary": {"type": "string"}}
    route_config: dict[str, Any] | None = None

    if output_mode == "decision":
        output_schema_props["needs_approval"] = {"type": "boolean"}
        route_config = {"field": "action", "enum": ["approve", "reject", "pending"]}
        output_schema_props["action"] = {"type": "string"}
    elif output_mode == "route":
        route_config = {"field": "route", "enum_from_edges": True}
        output_schema_props["route"] = {"type": "string"}
    elif output_mode == "extract" and config.get("output_fields"):
        for field_def in config["output_fields"]:
            name = field_def.get("name", field_def.get("key", ""))
            if name:
                output_schema_props[name] = {"type": field_def.get("type", "string")}
    elif output_mode == "custom" and config.get("output_schema"):
        new_config["output_contract"] = {
            "output_schema": config["output_schema"],
            "route": {"field": config.get("route_path", "route"), "enum_from_edges": True},
        }
        return new_config

    new_config["output_contract"] = {
        "output_schema": {
            "type": "object",
            "properties": output_schema_props,
            "required": list(output_schema_props.keys()),
        },
        "route": route_config,
    }

    return new_config


def legacy_default_graph(
    *,
    trigger_event: str,
    target_type: str | None,
    require_human_approval: bool,
    instructions: str,
) -> dict[str, Any]:
    capability = "moderate_comment | moderate_guestbook_entry"
    if (target_type or "").strip() == "comment":
        capability = "moderate_comment"
    elif (target_type or "").strip() == "guestbook":
        capability = "moderate_guestbook_entry"
    elif (target_type or "").strip() == "content":
        capability = "content_publish_review"

    return {
        "version": 2,
        "viewport": {"x": 0, "y": 0, "zoom": 0.92},
        "nodes": [
            {
                "id": "trigger-event",
                "type": "trigger.event",
                "label": "Event Trigger",
                "position": {"x": 90, "y": 160},
                "config": {
                    "event_type": trigger_event,
                    "target_type": target_type,
                    "matched_events": [trigger_event] if trigger_event else [],
                },
            },
            {
                "id": "ai-review",
                "type": "ai.task",
                "label": "AI Task",
                "position": {"x": 380, "y": 145},
                "config": {
                    "instructions": instructions,
                    "input_mode": "context_and_outputs",
                    "output_mode": "decision",
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "action": {"type": "string", "enum": ["approve", "reject", "pending"]},
                            "needs_approval": {"type": "boolean"},
                        },
                        "required": ["summary", "action", "needs_approval"],
                    },
                    "output_fields": [
                        {"name": "summary", "type": "string", "description": "给人看的简短摘要", "required": True},
                        {"name": "action", "type": "string", "description": "推荐的动作", "required": True},
                        {
                            "name": "needs_approval",
                            "type": "boolean",
                            "description": "是否需要人工审批",
                            "required": True,
                        },
                    ],
                    "route_path": "action",
                },
            },
            {
                "id": "approval-review",
                "type": "approval.review",
                "label": "Approval",
                "position": {"x": 990, "y": -30},
                "config": {
                    "approval_type": "moderation_decision",
                    "mode": "conditional",
                    "force": require_human_approval,
                    "required_from_path": "needs_approval",
                    "message_path": "summary",
                },
            },
            {
                "id": "apply-operation",
                "type": "operation.capability",
                "label": "Apply Action",
                "position": {"x": 990, "y": 170},
                "config": {
                    "operation_key": capability,
                    "risk_level": "high",
                    "argument_mappings": [
                        {"name": "action", "source": "approval", "path": "action"},
                        {"name": "reason", "source": "approval", "path": "reason"},
                    ],
                    "fallback_mode": "pending_on_ai_reject",
                },
            },
            {
                "id": "notify-webhook",
                "type": "notification.webhook",
                "label": "Webhook",
                "position": {"x": 1280, "y": 170},
                "config": {
                    "linked_subscription_ids": [],
                },
            },
        ],
        "edges": [
            {
                "id": "edge-trigger-ai",
                "source": "trigger-event",
                "target": "ai-review",
                "label": "",
                "type": "default",
                "config": {},
            },
            {
                "id": "edge-ai-operation",
                "source": "ai-review",
                "target": "apply-operation",
                "label": "",
                "type": "default",
                "config": {},
            },
            {
                "id": "edge-approval-operation",
                "source": "approval-review",
                "target": "apply-operation",
                "source_handle": "approval",
                "target_handle": "mount_1",
                "label": "",
                "type": "default",
                "config": {"kind": "control"},
            },
            {
                "id": "edge-operation-webhook",
                "source": "apply-operation",
                "target": "notify-webhook",
                "label": "",
                "type": "default",
                "config": {},
            },
        ],
    }


def normalize_graph_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    payload = deepcopy(raw or {})
    payload.setdefault("version", 2)
    payload.setdefault("viewport", {"x": 0, "y": 0, "zoom": 1})

    nodes = []
    for index, item in enumerate(payload.get("nodes") or [], start=1):
        if not isinstance(item, dict):
            continue
        node = deepcopy(item)
        node["id"] = str(node.get("id") or f"node-{index}")
        node["type"] = normalize_node_type(str(node.get("type") or "note"))
        node["label"] = str(node.get("label") or node["type"])
        node["position"] = dict(node.get("position") or {"x": 0, "y": 0})
        node["config"] = dict(node.get("config") or {})
        if node["type"] == "operation.capability" and "operation_key" not in node["config"]:
            node["config"]["operation_key"] = str(
                node["config"].get("capability") or node["config"].get("operation") or ""
            ).strip()
        if node["type"] == "ai.task" and "output_schema" not in node["config"]:
            node["config"]["output_schema"] = {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "action": {"type": "string"},
                    "needs_approval": {"type": "boolean"},
                },
            }
        if node["type"] == "ai.task":
            node["config"].setdefault("input_mode", "context_and_outputs")
            node["config"].setdefault("output_mode", "custom" if "output_schema" in node["config"] else "route")
            node["config"] = migrate_ai_node_config(node["config"])
        if node["type"] == "approval.review":
            node["config"].setdefault("approval_type", "manual_review")
            node["config"].setdefault("mode", "conditional")
            node["config"].setdefault("required_from_path", "needs_approval")
        if node["type"] == "notification.webhook":
            node["config"].pop("mode", None)
        nodes.append(node)
    nodes_by_id = {str(node.get("id") or ""): node for node in nodes}

    edges = []
    ai_input_slots_by_target: dict[str, list[str]] = {}
    ai_output_slots_by_source: dict[str, list[str]] = {}
    ai_mount_slots_by_target: dict[str, list[str]] = {}
    for index, item in enumerate(payload.get("edges") or [], start=1):
        if not isinstance(item, dict):
            continue
        edge = deepcopy(item)
        edge["id"] = str(edge.get("id") or f"edge-{index}")
        edge["source"] = str(edge.get("source") or "")
        edge["target"] = str(edge.get("target") or "")
        edge["source_handle"] = str(edge.get("source_handle") or "").strip() or None
        edge["target_handle"] = str(edge.get("target_handle") or "").strip() or None
        edge["label"] = str(edge.get("label") or "")
        edge["type"] = str(edge.get("type") or "default")
        edge["config"] = dict(edge.get("config") or {})

        source_type = str(dict(nodes_by_id.get(edge["source"]) or {}).get("type") or "")
        target_type = str(dict(nodes_by_id.get(edge["target"]) or {}).get("type") or "")

        if source_type == "tool.query" and target_type == "ai.task":
            edge["source_handle"] = edge["source_handle"] or "tool"
            requested_handle = edge["target_handle"]
            assigned_mounts = ai_mount_slots_by_target.setdefault(edge["target"], [])
            if (
                requested_handle in {"mount_1", "mount_2", "mount_3", "mount_4"}
                and requested_handle not in assigned_mounts
            ):
                assigned_mounts.append(requested_handle)
            else:
                for candidate in ("mount_1", "mount_2", "mount_3", "mount_4"):
                    if candidate not in assigned_mounts:
                        edge["target_handle"] = candidate
                        assigned_mounts.append(candidate)
                        break
        elif source_type.startswith("trigger.") and target_type == "ai.task":
            requested_handle = edge["target_handle"]
            assigned_mounts = ai_mount_slots_by_target.setdefault(edge["target"], [])
            if (
                requested_handle in {"mount_1", "mount_2", "mount_3", "mount_4"}
                and requested_handle not in assigned_mounts
            ):
                assigned_mounts.append(requested_handle)
            else:
                for candidate in ("mount_1", "mount_2", "mount_3", "mount_4"):
                    if candidate not in assigned_mounts:
                        edge["target_handle"] = candidate
                        assigned_mounts.append(candidate)
                        break
        elif source_type == "approval.review":
            edge["source_handle"] = "approval"
            requested_handle = edge["target_handle"]
            assigned_mounts = ai_mount_slots_by_target.setdefault(edge["target"], [])
            if (
                requested_handle in {"mount_1", "mount_2", "mount_3", "mount_4"}
                and requested_handle not in assigned_mounts
            ):
                assigned_mounts.append(requested_handle)
            else:
                for candidate in ("mount_1", "mount_2", "mount_3", "mount_4"):
                    if candidate not in assigned_mounts:
                        edge["target_handle"] = candidate
                        assigned_mounts.append(candidate)
                        break
            edge["config"].pop("match", None)
            edge["config"].pop("match_value", None)
        elif source_type == "apply.action" and target_type == "ai.task":
            requested_handle = edge["target_handle"]
            assigned_mounts = ai_mount_slots_by_target.setdefault(edge["target"], [])
            if (
                requested_handle in {"mount_1", "mount_2", "mount_3", "mount_4"}
                and requested_handle not in assigned_mounts
            ):
                assigned_mounts.append(requested_handle)
            else:
                for candidate in ("mount_1", "mount_2", "mount_3", "mount_4"):
                    if candidate not in assigned_mounts:
                        edge["target_handle"] = candidate
                        assigned_mounts.append(candidate)
                        break
        elif source_type == "ai.task":
            assigned_outputs = ai_output_slots_by_source.setdefault(edge["source"], [])
            requested_handle = edge["source_handle"]
            if requested_handle in {"output_1", "output_2"} and requested_handle not in assigned_outputs:
                assigned_outputs.append(requested_handle)
            else:
                for candidate in ("output_1", "output_2"):
                    if candidate not in assigned_outputs:
                        edge["source_handle"] = candidate
                        assigned_outputs.append(candidate)
                        break
                if edge["source_handle"] not in {"output_1", "output_2"}:
                    edge["source_handle"] = "output_1"
        elif target_type == "ai.task":
            assigned_slots = ai_input_slots_by_target.setdefault(edge["target"], [])
            requested_handle = edge["target_handle"]
            if requested_handle in {"input_1", "input_2", "input_3"} and requested_handle not in assigned_slots:
                assigned_slots.append(requested_handle)
            else:
                for candidate in ("input_1", "input_2", "input_3"):
                    if candidate not in assigned_slots:
                        edge["target_handle"] = candidate
                        assigned_slots.append(candidate)
                        break
        edges.append(edge)

    payload["nodes"] = nodes
    payload["edges"] = edges
    return payload


def default_trigger_bindings_from_legacy(raw: dict[str, Any]) -> list[dict[str, Any]]:
    trigger_event = str(raw.get("trigger_event") or "").strip()
    target_type = str(raw.get("target_type") or "").strip() or None
    if not trigger_event:
        return []
    matched_events = [trigger_event]
    if trigger_event == "engagement.pending":
        matched_events = ["engagement.pending", "comment.pending", "guestbook.pending"]
    return [
        {
            "id": "event-trigger",
            "type": "trigger.event",
            "label": trigger_event,
            "enabled": bool(raw.get("enabled", True)),
            "config": {
                "event_type": trigger_event,
                "matched_events": matched_events,
                "target_type": target_type,
            },
        }
    ]


def normalize_trigger_bindings_payload(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        binding = deepcopy(item)
        binding["id"] = str(binding.get("id") or f"binding-{index}")
        binding["type"] = normalize_binding_type(str(binding.get("type") or "trigger.event"))
        binding["label"] = str(binding.get("label") or binding["id"])
        binding["enabled"] = bool(binding.get("enabled", True))
        binding["config"] = dict(binding.get("config") or {})
        items.append(binding)
    return items


def normalize_runtime_policy_payload(raw: Any) -> dict[str, Any]:
    base = AgentWorkflowRuntimePolicy().model_dump(mode="json")
    if isinstance(raw, dict):
        base.update(raw)
    return base


def legacy_to_v2_workflow(raw: dict[str, Any]) -> dict[str, Any]:
    schema_version = int(raw.get("schema_version") or 1)
    if schema_version >= 2 and isinstance(raw.get("graph"), dict) and isinstance(raw.get("trigger_bindings"), list):
        normalized = deepcopy(raw)
        normalized["schema_version"] = 2
        normalized["graph"] = normalize_graph_payload(dict(raw.get("graph") or {}))
        normalized["trigger_bindings"] = normalize_trigger_bindings_payload(raw.get("trigger_bindings"))
        normalized["runtime_policy"] = normalize_runtime_policy_payload(raw.get("runtime_policy"))
        normalized["summary"] = dict(raw.get("summary") or {})
        return normalized

    instructions = str(raw.get("instructions") or "").strip()
    require_human_approval = bool(raw.get("require_human_approval", False))
    trigger_event = str(raw.get("trigger_event") or "").strip()
    target_type = str(raw.get("target_type") or "").strip() or None
    graph_payload = (
        raw.get("graph")
        if isinstance(raw.get("graph"), dict)
        else legacy_default_graph(
            trigger_event=trigger_event,
            target_type=target_type,
            require_human_approval=require_human_approval,
            instructions=instructions,
        )
    )
    return {
        "schema_version": 2,
        "key": str(raw.get("key") or ""),
        "name": str(raw.get("name") or raw.get("key") or ""),
        "description": str(raw.get("description") or ""),
        "enabled": bool(raw.get("enabled", True)),
        "graph": normalize_graph_payload(graph_payload),
        "trigger_bindings": default_trigger_bindings_from_legacy(raw),
        "runtime_policy": normalize_runtime_policy_payload(
            {
                "approval_mode": "always" if require_human_approval else "risk_based",
                "allow_high_risk_without_approval": False,
            }
        ),
        "summary": {"narrative": str(raw.get("description") or "")},
    }


def derive_legacy_fields(payload: dict[str, Any]) -> dict[str, Any]:
    trigger_event = None
    target_type = None
    for binding in payload.get("trigger_bindings") or []:
        if str(binding.get("type") or "") != "trigger.event" or not binding.get("enabled", True):
            continue
        config = dict(binding.get("config") or {})
        matched_events = [str(item).strip() for item in config.get("matched_events") or [] if str(item).strip()]
        trigger_event = str(config.get("event_type") or (matched_events[0] if matched_events else "")).strip() or None
        target_type = str(config.get("target_type") or "").strip() or None
        break

    instructions = ""
    require_human_approval = False
    for node in payload.get("graph", {}).get("nodes") or []:
        node_type = str(node.get("type") or "")
        config = dict(node.get("config") or {})
        if not instructions and node_type == "ai.task":
            instructions = str(config.get("instructions") or config.get("prompt") or "").strip()
        if node_type == "approval.review":
            mode = str(config.get("mode") or "conditional").strip()
            require_human_approval = require_human_approval or bool(config.get("force")) or mode == "always"
    return {
        "trigger_event": trigger_event,
        "target_type": target_type,
        "instructions": instructions,
        "require_human_approval": require_human_approval,
    }


def derive_summary(payload: dict[str, Any]) -> AgentWorkflowSummaryRead:
    nodes = list(payload.get("graph", {}).get("nodes") or [])
    trigger_labels = [
        str(binding.get("label") or binding.get("id") or "")
        for binding in payload.get("trigger_bindings") or []
        if binding.get("enabled", True)
    ]
    operation_nodes = [item for item in nodes if str(item.get("type") or "").startswith("operation.")]
    high_risk_operation_count = 0
    for node in operation_nodes:
        risk = str(dict(node.get("config") or {}).get("risk_level") or "low").strip().lower()
        if risk == "high":
            high_risk_operation_count += 1
    return AgentWorkflowSummaryRead(
        trigger_labels=trigger_labels,
        node_count=len(nodes),
        operation_count=len(operation_nodes),
        high_risk_operation_count=high_risk_operation_count,
        built_from_template=str(dict(payload.get("summary") or {}).get("built_from_template") or "") or None,
        narrative=str(dict(payload.get("summary") or {}).get("narrative") or payload.get("description") or ""),
    )


def normalize_workflow_dict(
    payload: dict[str, Any],
    *,
    workflow_key: str,
    workflow_name: str,
    workflow_description: str,
    built_in: bool,
    built_in_keys: set[str],
) -> dict[str, Any]:
    normalized = legacy_to_v2_workflow(payload)
    return {
        **normalized,
        "key": workflow_key,
        "name": workflow_name,
        "description": workflow_description,
        "graph": AgentWorkflowGraph.model_validate(normalized["graph"]).model_dump(mode="json"),
        "trigger_bindings": [
            AgentWorkflowTriggerBinding.model_validate(item).model_dump(mode="json")
            for item in normalized["trigger_bindings"]
        ],
        "runtime_policy": AgentWorkflowRuntimePolicy.model_validate(normalized["runtime_policy"]).model_dump(
            mode="json"
        ),
        "summary": derive_summary(normalized).model_dump(mode="json"),
        "built_in": built_in or workflow_key in built_in_keys,
        **derive_legacy_fields(normalized),
    }
