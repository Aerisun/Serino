from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from aerisun.domain.automation.compiler import (
    derive_ai_output_schema as compile_ai_output_schema,
)
from aerisun.domain.automation.operations import list_operation_definitions
from aerisun.domain.automation.schemas import (
    ActionSurfaceRead,
    AgentWorkflowCatalogApprovalTypeRead,
    AgentWorkflowCatalogNodeTypeRead,
    AgentWorkflowCatalogOperationRead,
    AgentWorkflowCatalogOptionRead,
    AgentWorkflowCatalogPortRead,
    AgentWorkflowCatalogRead,
    AgentWorkflowCatalogTriggerTypeRead,
    AgentWorkflowExpressionCatalogRead,
    AgentWorkflowTemplateRead,
    AgentWorkflowVariableSourceRead,
    ToolSurfaceRead,
)
from aerisun.domain.automation.settings import list_agent_workflows
from aerisun.domain.automation.tool_surface import list_action_surfaces, list_tool_surfaces


def _port(
    port_id: str,
    label: str,
    side: str,
    description: str = "",
    *,
    match_values: list[str] | None = None,
    data_schema: dict[str, Any] | None = None,
    required: bool = True,
):
    return AgentWorkflowCatalogPortRead(
        id=port_id,
        label=label,
        side=side,
        description=description,
        match_values=match_values or [],
        data_schema=data_schema,
        required=required,
    )


def _node_types() -> list[AgentWorkflowCatalogNodeTypeRead]:
    return [
        AgentWorkflowCatalogNodeTypeRead(
            type="trigger.event",
            label="事件触发",
            category="trigger",
            description="当平台中的某个事件发生时启动流程。",
            icon="zap",
            default_config={"event_type": "", "target_type": ""},
            config_schema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "target_type": {"type": ["string", "null"]},
                    "matched_events": {"type": "array", "items": {"type": "string"}},
                },
            },
            input_ports=[],
            output_ports=[
                _port(
                    "next",
                    "Next",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "event_type": {"type": "string"},
                            "target_type": {"type": "string"},
                            "target_id": {"type": "string"},
                            "context_payload": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="trigger.webhook",
            label="Webhook 触发",
            category="trigger",
            description="当外部系统通过 Webhook 调用时启动流程。",
            icon="webhook",
            default_config={"path": "", "secret": "", "target_type": ""},
            config_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "secret": {"type": "string"},
                    "target_type": {"type": ["string", "null"]},
                },
            },
            input_ports=[],
            output_ports=[
                _port(
                    "next",
                    "Next",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "headers": {"type": "object"},
                            "body": {"type": "object", "additionalProperties": True},
                            "query_params": {"type": "object"},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="trigger.manual",
            label="手动触发",
            category="trigger",
            description="由管理员在后台手动启动流程。",
            icon="play",
            default_config={},
            config_schema={"type": "object", "properties": {}},
            input_ports=[],
            output_ports=[
                _port(
                    "next",
                    "Next",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "inputs": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="trigger.schedule",
            label="定时触发",
            category="trigger",
            description="按固定间隔或 Cron 定时启动流程。",
            icon="clock-3",
            default_config={"interval_seconds": 300},
            config_schema={
                "type": "object",
                "properties": {
                    "interval_seconds": {"type": "integer", "minimum": 30},
                    "cron": {"type": "string"},
                    "target_type": {"type": ["string", "null"]},
                },
            },
            input_ports=[],
            output_ports=[
                _port(
                    "next",
                    "Next",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "scheduled_at": {"type": "string", "format": "date-time"},
                            "inputs": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="flow.condition",
            label="条件分支",
            category="flow",
            description="根据条件表达式决定流程后续走向。",
            icon="git-branch",
            default_config={"expression": ""},
            config_schema={"type": "object", "properties": {"expression": {"type": "string"}}},
            input_ports=[_port("in", "In", "left")],
            output_ports=[
                _port(
                    "true",
                    "True",
                    "right",
                    match_values=["true"],
                    data_schema={
                        "type": "object",
                        "properties": {
                            "result": {"type": "boolean"},
                            "expression": {"type": "string"},
                        },
                        "required": ["result", "expression"],
                    },
                ),
                _port(
                    "false",
                    "False",
                    "right",
                    match_values=["false"],
                    data_schema={
                        "type": "object",
                        "properties": {
                            "result": {"type": "boolean"},
                            "expression": {"type": "string"},
                        },
                        "required": ["result", "expression"],
                    },
                ),
                _port(
                    "default",
                    "Default",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "result": {"type": "boolean"},
                            "expression": {"type": "string"},
                        },
                        "required": ["result", "expression"],
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="flow.delay",
            label="延时等待",
            category="flow",
            description="让流程暂停一段时间后再继续。",
            icon="timer",
            default_config={"delay_seconds": 60},
            config_schema={
                "type": "object",
                "properties": {
                    "delay_seconds": {"type": "integer", "minimum": 1},
                    "until_path": {"type": "string"},
                },
            },
            input_ports=[
                _port("in", "In", "left"),
                _port(
                    "mount_approval", "审核", "top", description="Approval gate mount", data_schema=None, required=False
                ),
            ],
            output_ports=[
                _port(
                    "done",
                    "Done",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "resumed_at": {"type": "string", "format": "date-time"},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="flow.poll",
            label="轮询检测",
            category="flow",
            description="反复执行查询动作，直到满足成功条件。",
            icon="refresh-cw",
            default_config={
                "interval_seconds": 60,
                "max_attempts": 10,
                "success_expression": "poll_result.status == 'done'",
            },
            config_schema={
                "type": "object",
                "properties": {
                    "interval_seconds": {"type": "integer", "minimum": 5},
                    "max_attempts": {"type": "integer", "minimum": 1},
                    "success_expression": {"type": "string"},
                    "operation_type": {"type": "string"},
                    "operation_key": {"type": "string"},
                    "argument_mappings": {"type": "array", "items": {"type": "object"}},
                },
            },
            input_ports=[
                _port("in", "In", "left"),
                _port(
                    "mount_approval", "审核", "top", description="Approval gate mount", data_schema=None, required=False
                ),
            ],
            output_ports=[
                _port(
                    "done",
                    "Done",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["done", "timeout"]},
                            "attempt_count": {"type": "integer"},
                            "last_result": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
                _port(
                    "timeout",
                    "Timeout",
                    "right",
                    match_values=["timeout"],
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["done", "timeout"]},
                            "attempt_count": {"type": "integer"},
                            "last_result": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="flow.wait_for_event",
            label="等待事件",
            category="flow",
            description="暂停流程，直到等到指定事件后再恢复。",
            icon="pause-circle",
            default_config={"event_type": "", "timeout_seconds": 3600},
            config_schema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "target_type": {"type": ["string", "null"]},
                    "timeout_seconds": {"type": "integer", "minimum": 1},
                },
            },
            input_ports=[_port("in", "In", "left")],
            output_ports=[
                _port(
                    "matched",
                    "Matched",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["matched", "timeout"]},
                            "event": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
                _port(
                    "timeout",
                    "Timeout",
                    "right",
                    match_values=["timeout"],
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["matched", "timeout"]},
                            "event": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="note",
            label="备注",
            category="utility",
            description="只用于写说明，不执行任何动作。",
            icon="sticky-note",
            default_config={"content": ""},
            config_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Human-readable note content"},
                },
            },
            input_ports=[_port("in", "In", "left", required=False)],
            output_ports=[],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="ai.task",
            label="AI 任务",
            category="ai",
            description="AI 壳节点。输入输出协议由端口连接自动推导，节点自身只负责提示词、模式和循环策略。",
            icon="bot",
            default_config={
                "instructions": "",
                "mode": "direct",
                "loop_max_rounds": 6,
                "tool_usage_mode": "recommended",
                "minimum_tool_calls": 1,
                "input_slots": {
                    "input_1": {"note": ""},
                    "input_2": {"note": ""},
                    "input_3": {"note": ""},
                },
            },
            config_schema={
                "type": "object",
                "properties": {
                    "instructions": {"type": "string", "description": "System prompt for the AI agent"},
                    "mode": {
                        "type": "string",
                        "enum": ["direct", "loop"],
                        "description": "direct = single pass, loop = iterative reasoning/tool exploration",
                    },
                    "loop_max_rounds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Maximum loop rounds when mode=loop",
                    },
                    "tool_usage_mode": {
                        "type": "string",
                        "enum": ["optional", "recommended", "required"],
                        "description": "Whether the AI should use mounted readonly tools or action capabilities before finalizing the answer.",
                    },
                    "minimum_tool_calls": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Minimum number of mounted capability calls required when tool_usage_mode=required.",
                    },
                    "input_slots": {
                        "type": "object",
                        "description": "Per-input-slot prompt notes shown to the AI for mounted upstream data.",
                        "properties": {
                            "input_1": {
                                "type": "object",
                                "properties": {
                                    "note": {"type": "string"},
                                },
                            },
                            "input_2": {
                                "type": "object",
                                "properties": {
                                    "note": {"type": "string"},
                                },
                            },
                            "input_3": {
                                "type": "object",
                                "properties": {
                                    "note": {"type": "string"},
                                },
                            },
                        },
                    },
                    # Internal compiled/runtime fields kept available, but no longer
                    # intended to be the primary user-edit surface.
                    "input_contract": {
                        "type": "object",
                        "properties": {
                            "fields": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "key": {"type": "string"},
                                        "field_schema": {"type": "object"},
                                        "required": {"type": "boolean", "default": True},
                                        "selector": {
                                            "type": "object",
                                            "properties": {
                                                "source": {
                                                    "type": "string",
                                                    "enum": [
                                                        "trigger",
                                                        "webhook",
                                                        "node_output",
                                                        "artifact",
                                                        "literal",
                                                    ],
                                                },
                                                "node_id": {"type": "string"},
                                                "port": {"type": "string"},
                                                "path": {"type": "string"},
                                                "value": {},
                                            },
                                        },
                                    },
                                    "required": ["key"],
                                },
                            },
                        },
                    },
                    "tool_contract": {
                        "type": "object",
                        "description": "Which tool surfaces the agent can use",
                        "properties": {
                            "tools": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "tool_surface keys",
                            },
                        },
                    },
                    "output_contract": {
                        "type": "object",
                        "description": "What data the agent must produce",
                        "properties": {
                            "output_schema": {"type": "object", "description": "JSON Schema for data output"},
                            "route": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string", "description": "Route field name"},
                                    "enum": {"type": "array", "items": {"type": "string"}},
                                    "enum_from_edges": {"type": "boolean", "default": False},
                                },
                            },
                        },
                    },
                },
            },
            input_ports=[
                _port(
                    "input_1",
                    "输入口 1",
                    "left",
                    description="Primary structured input",
                    data_schema=None,
                    required=False,
                ),
                _port(
                    "input_2",
                    "输入口 2",
                    "left",
                    description="Secondary structured input",
                    data_schema=None,
                    required=False,
                ),
                _port(
                    "input_3",
                    "输入口 3",
                    "left",
                    description="Additional structured input",
                    data_schema=None,
                    required=False,
                ),
                _port(
                    "mount_1",
                    "挂载口 1",
                    "top",
                    description="Generic mount slot for trigger, approval, readonly tools, or actions",
                    data_schema=None,
                    required=False,
                ),
                _port(
                    "mount_2",
                    "挂载口 2",
                    "top",
                    description="Generic mount slot for trigger, approval, readonly tools, or actions",
                    data_schema=None,
                    required=False,
                ),
                _port(
                    "mount_3",
                    "挂载口 3",
                    "top",
                    description="Generic mount slot for trigger, approval, readonly tools, or actions",
                    data_schema=None,
                    required=False,
                ),
                _port(
                    "mount_4",
                    "挂载口 4",
                    "top",
                    description="Generic mount slot for trigger, approval, readonly tools, or actions",
                    data_schema=None,
                    required=False,
                ),
            ],
            output_ports=[
                _port(
                    "output_1",
                    "输出口 1",
                    "right",
                    description="Structured output for downstream consumers",
                    data_schema=None,
                    required=False,
                ),
                _port(
                    "output_2",
                    "输出口 2",
                    "right",
                    description="Structured output for downstream consumers",
                    data_schema=None,
                    required=False,
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="tool.query",
            label="只读工具",
            category="tool",
            description="把一组只读工具挂载到 AI 节点上，供 AI 在运行时按需调用。",
            icon="server",
            default_config={"surface_keys": []},
            config_schema={
                "type": "object",
                "properties": {
                    "surface_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Readonly tool surface keys to mount on the AI task.",
                    },
                },
            },
            input_ports=[],
            output_ports=[
                _port("tool", "Tool", "right", description="Tool mount output", data_schema=None, required=False)
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="apply.action",
            label="执行动作",
            category="operation",
            description="执行当前 workflow pack 中的 action surface。",
            icon="cable",
            default_config={"surface_key": "", "input_selector": {"source": "node_output", "path": "surface_ref"}},
            config_schema={
                "type": "object",
                "properties": {
                    "surface_key": {"type": "string"},
                    "input_selector": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "path": {"type": "string"},
                        },
                    },
                },
                "required": ["surface_key"],
            },
            input_ports=[
                _port("in", "In", "left", data_schema=None, required=False),
                _port(
                    "mount_approval", "审核", "top", description="Approval gate mount", data_schema=None, required=False
                ),
            ],
            output_ports=[
                _port(
                    "success",
                    "Success",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "applied": {"type": "boolean"},
                            "action": {"type": "string"},
                            "reason": {"type": "string"},
                            "surface_key": {"type": "string"},
                            "node": {"type": "object"},
                            "execution_summary": {"type": "string"},
                            "execution_result": {"type": "object", "additionalProperties": True},
                            "result": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
                _port(
                    "error",
                    "Error",
                    "right",
                    match_values=["error"],
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "applied": {"type": "boolean"},
                            "action": {"type": "string"},
                            "reason": {"type": "string"},
                            "surface_key": {"type": "string"},
                            "node": {"type": "object"},
                            "execution_summary": {"type": "string"},
                            "execution_result": {"type": "object", "additionalProperties": True},
                            "result": {"type": "object", "additionalProperties": True},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="approval.review",
            label="人工审批",
            category="approval",
            description="请求人工审批，并向后续高风险节点发放审批令牌。",
            icon="shield-check",
            default_config={
                "approval_type": "manual_review",
                "mode": "conditional",
                "required_from_path": "needs_approval",
            },
            config_schema={
                "type": "object",
                "properties": {
                    "approval_type": {"type": "string"},
                    "mode": {"type": "string", "enum": ["always", "conditional", "never"]},
                    "required_from_path": {"type": "string"},
                    "message_path": {"type": "string"},
                    "force": {"type": "boolean"},
                },
            },
            input_ports=[],
            output_ports=[
                _port(
                    "approval",
                    "Approval",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "decision": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                            },
                            "token": {
                                "type": "object",
                                "properties": {
                                    "granted": {"type": "boolean"},
                                    "auto": {"type": "boolean"},
                                    "approval_type": {"type": "string"},
                                },
                            },
                        },
                    },
                ),
            ],
            risk_level="high",
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="operation.capability",
            label="平台能力调用",
            category="operation",
            description="直接调用平台后端能力。",
            icon="cable",
            default_config={"operation_key": "", "argument_mappings": []},
            config_schema={
                "type": "object",
                "properties": {
                    "operation_key": {"type": "string"},
                    "argument_mappings": {"type": "array", "items": {"type": "object"}},
                    "risk_level": {"type": "string"},
                    "route_path": {"type": "string"},
                    "fallback_mode": {"type": "string"},
                },
            },
            input_ports=[
                _port("in", "In", "left", data_schema=None, required=False),
                _port(
                    "mount_approval", "审核", "top", description="Approval gate mount", data_schema=None, required=False
                ),
            ],
            output_ports=[
                _port(
                    "success",
                    "Success",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "applied": {"type": "boolean"},
                            "action": {"type": "string"},
                            "reason": {"type": "string"},
                            "node": {"type": "object"},
                            "execution_summary": {"type": "string"},
                            "execution_result": {"type": "object", "additionalProperties": True},
                            "execution": {"type": "object"},
                        },
                    },
                ),
                _port(
                    "error",
                    "Error",
                    "right",
                    match_values=["error"],
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "applied": {"type": "boolean"},
                            "action": {"type": "string"},
                            "reason": {"type": "string"},
                            "node": {"type": "object"},
                            "execution_summary": {"type": "string"},
                            "execution_result": {"type": "object", "additionalProperties": True},
                            "execution": {"type": "object"},
                        },
                    },
                ),
            ],
        ),
        AgentWorkflowCatalogNodeTypeRead(
            type="notification.webhook",
            label="Webhook 通知",
            category="notification",
            description="把数据按映射后的结构发送给 Webhook。",
            icon="send",
            default_config={"linked_subscription_ids": [], "format_requirements": ""},
            config_schema={
                "type": "object",
                "properties": {
                    "linked_subscription_ids": {"type": "array", "items": {"type": "string"}},
                    "event_type": {"type": "string"},
                    "format_requirements": {"type": "string"},
                },
            },
            input_ports=[_port("in", "In", "left")],
            output_ports=[
                _port(
                    "done",
                    "Done",
                    "right",
                    data_schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "delivery_count": {"type": "integer"},
                            "formatted_text": {"type": "string"},
                        },
                    },
                ),
            ],
        ),
    ]


def workflow_node_type_registry() -> dict[str, AgentWorkflowCatalogNodeTypeRead]:
    return {item.type: item for item in _node_types()}


def _trigger_types() -> list[AgentWorkflowCatalogTriggerTypeRead]:
    return [
        AgentWorkflowCatalogTriggerTypeRead(
            type="trigger.event",
            label="平台事件",
            description="由平台内部业务事件触发。",
            config_schema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "matched_events": {"type": "array", "items": {"type": "string"}},
                    "target_type": {"type": ["string", "null"]},
                },
            },
            example_config={"event_type": "comment.pending", "target_type": "comment"},
            supports_target_types=["comment", "guestbook", "content", "asset", "record"],
        ),
        AgentWorkflowCatalogTriggerTypeRead(
            type="trigger.webhook",
            label="Webhook",
            description="由外部系统的 Webhook 请求触发。",
            config_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "secret": {"type": "string"},
                    "target_type": {"type": ["string", "null"]},
                },
            },
            example_config={"path": "incoming/order-sync", "secret": "dev-secret"},
        ),
        AgentWorkflowCatalogTriggerTypeRead(
            type="trigger.manual",
            label="手动触发",
            description="由后台手动执行，用于测试或受控运行。",
            config_schema={"type": "object", "properties": {}},
            example_config={},
        ),
        AgentWorkflowCatalogTriggerTypeRead(
            type="trigger.schedule",
            label="定时触发",
            description="按间隔或 Cron 定时触发。",
            config_schema={
                "type": "object",
                "properties": {
                    "interval_seconds": {"type": "integer", "minimum": 30},
                    "cron": {"type": "string"},
                    "target_type": {"type": ["string", "null"]},
                },
            },
            example_config={"interval_seconds": 300},
        ),
    ]


def _approval_types() -> list[AgentWorkflowCatalogApprovalTypeRead]:
    return [
        AgentWorkflowCatalogApprovalTypeRead(
            key="manual_review",
            label="人工复核",
            description="标准的人工通过 / 拒绝审批。",
            config_schema={
                "type": "object",
                "properties": {
                    "message_path": {"type": "string"},
                    "required_from_path": {"type": "string"},
                },
            },
        ),
        AgentWorkflowCatalogApprovalTypeRead(
            key="moderation_decision",
            label="审核决策",
            description="用于评论 / 留言审核的通过、拒绝或转人工复核。",
            config_schema={
                "type": "object",
                "properties": {
                    "message_path": {"type": "string"},
                    "required_from_path": {"type": "string"},
                },
            },
        ),
    ]


def _expression_catalog() -> AgentWorkflowExpressionCatalogRead:
    return AgentWorkflowExpressionCatalogRead(
        helpers=[
            {"name": "path", "description": "Look up a dotted path from the current evaluation environment."},
            {"name": "contains", "description": "Return true when the second value exists inside the first value."},
            {"name": "startswith", "description": "Check string prefix."},
            {"name": "endswith", "description": "Check string suffix."},
            {"name": "lower", "description": "Lowercase one string."},
            {"name": "upper", "description": "Uppercase one string."},
            {"name": "len", "description": "Return the length of a string, array, or object."},
        ],
        variables=[
            {"name": "inputs", "description": "Manual/test input payload."},
            {"name": "context_payload", "description": "Current trigger context."},
            {"name": "node_outputs", "description": "Outputs from previously completed nodes."},
            {"name": "artifacts", "description": "Named intermediate values produced by transform nodes."},
            {"name": "result_payload", "description": "Latest operation result payload."},
            {"name": "approval_token", "description": "Approval grant state for downstream high-risk operations."},
        ],
        examples=[
            "path('context_payload.author_name') == 'Rowan'",
            "contains(lower(path('node_outputs.ai-review.summary')), 'spam')",
            "path('node_outputs.fetch-status.status') in ['ready', 'published']",
        ],
    )


def _variable_sources() -> list[AgentWorkflowVariableSourceRead]:
    return [
        AgentWorkflowVariableSourceRead(key="inputs", label="手动输入", description="手动运行或测试运行时输入的数据。"),
        AgentWorkflowVariableSourceRead(
            key="context_payload", label="触发上下文", description="当前触发器带进来的事件数据。"
        ),
        AgentWorkflowVariableSourceRead(
            key="node_outputs", label="节点输出", description="前面节点执行完成后的输出结果。"
        ),
        AgentWorkflowVariableSourceRead(
            key="artifacts", label="中间数据", description="transform 节点整理出来的中间数据。"
        ),
        AgentWorkflowVariableSourceRead(
            key="result_payload", label="最近执行结果", description="最近一次执行动作的结果。"
        ),
        AgentWorkflowVariableSourceRead(key="approval", label="审批结果", description="最近一次人工审批的结果。"),
        AgentWorkflowVariableSourceRead(key="literal", label="固定值", description="手动填写的固定值。"),
    ]


def _event_trigger_options() -> list[AgentWorkflowCatalogOptionRead]:
    return [
        AgentWorkflowCatalogOptionRead(
            value="engagement.pending",
            label="评论或留言进入待处理阶段时",
            description="评论和留言进入待处理阶段时都会触发，适合做统一审核、提醒或打标流程。",
            system_value="engagement.pending",
            target_types=["comment", "guestbook"],
            payload_fields=[
                {"field": "body_preview", "description": "正文预览"},
                {"field": "author_name", "description": "提交者昵称"},
                {"field": "comment_id", "description": "评论 ID，留言时为空"},
                {"field": "entry_id", "description": "留言 ID，评论时为空"},
            ],
            example_payload={"body_preview": "你好，写得很好。", "author_name": "Rowan", "comment_id": "123"},
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="comment.pending",
            label="评论进入待处理阶段时",
            description="新评论进入待审核队列时触发，适合自动审核、提醒管理员或做风险分析。",
            system_value="comment.pending",
            target_types=["comment"],
            payload_fields=[
                {"field": "comment_id", "description": "评论 ID"},
                {"field": "content_type", "description": "所属内容类型"},
                {"field": "content_slug", "description": "所属内容 slug"},
                {"field": "author_name", "description": "评论作者"},
                {"field": "body_preview", "description": "评论正文预览"},
            ],
            example_payload={"comment_id": "123", "content_type": "posts", "content_slug": "hello-world"},
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="guestbook.pending",
            label="留言进入待处理阶段时",
            description="新留言进入待审核队列时触发，适合自动审核、提醒管理员或做分流。",
            system_value="guestbook.pending",
            target_types=["guestbook"],
            payload_fields=[
                {"field": "entry_id", "description": "留言 ID"},
                {"field": "author_name", "description": "留言作者"},
                {"field": "body_preview", "description": "留言正文预览"},
            ],
            example_payload={"entry_id": "guestbook-1", "author_name": "Visitor"},
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="comment.approve",
            label="评论被通过时",
            description="评论审核通过后触发，适合做通知、积分、统计或同步。",
            system_value="comment.approve",
            target_types=["comment"],
            payload_fields=[
                {"field": "comment_id", "description": "评论 ID"},
                {"field": "action", "description": "本次动作"},
                {"field": "reason", "description": "审核原因或备注"},
            ],
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="comment.reject",
            label="评论被拒绝时",
            description="评论被拒绝后触发，适合做记录、告警或额外人工流程。",
            system_value="comment.reject",
            target_types=["comment"],
            payload_fields=[
                {"field": "comment_id", "description": "评论 ID"},
                {"field": "action", "description": "本次动作"},
                {"field": "reason", "description": "拒绝原因或备注"},
            ],
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="comment.delete",
            label="评论被删除时",
            description="评论被删除后触发，适合做审计记录或外部同步。",
            system_value="comment.delete",
            target_types=["comment"],
            payload_fields=[
                {"field": "comment_id", "description": "评论 ID"},
                {"field": "action", "description": "本次动作"},
                {"field": "reason", "description": "删除原因或备注"},
            ],
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="guestbook.approve",
            label="留言被通过时",
            description="留言审核通过后触发，适合做通知、展示同步或记录。",
            system_value="guestbook.approve",
            target_types=["guestbook"],
            payload_fields=[
                {"field": "entry_id", "description": "留言 ID"},
                {"field": "action", "description": "本次动作"},
                {"field": "reason", "description": "审核原因或备注"},
            ],
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="guestbook.reject",
            label="留言被拒绝时",
            description="留言被拒绝后触发，适合做审计、提醒或补充处理。",
            system_value="guestbook.reject",
            target_types=["guestbook"],
            payload_fields=[
                {"field": "entry_id", "description": "留言 ID"},
                {"field": "action", "description": "本次动作"},
                {"field": "reason", "description": "拒绝原因或备注"},
            ],
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="guestbook.delete",
            label="留言被删除时",
            description="留言被删除后触发，适合做审计记录或外部同步。",
            system_value="guestbook.delete",
            target_types=["guestbook"],
            payload_fields=[
                {"field": "entry_id", "description": "留言 ID"},
                {"field": "action", "description": "本次动作"},
                {"field": "reason", "description": "删除原因或备注"},
            ],
            group_key="community",
            group_label="社区互动",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.publish_requested",
            label="内容发起发布申请时",
            description="内容进入发布申请流程时触发，适合做发布检查、补充处理或通知。",
            system_value="content.publish_requested",
            target_types=["content"],
            payload_fields=[
                {"field": "content_id", "description": "内容 ID"},
                {"field": "content_type", "description": "内容类型"},
                {"field": "title", "description": "内容标题"},
                {"field": "summary", "description": "内容摘要"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.created",
            label="内容被创建时",
            description="后台新建内容后触发，适合做初始化、同步或自动补全。",
            system_value="content.created",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_id", "description": "内容 ID"},
                {"field": "slug", "description": "内容 slug"},
                {"field": "title", "description": "标题"},
                {"field": "status", "description": "状态"},
                {"field": "visibility", "description": "可见性"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.updated",
            label="内容被更新时",
            description="后台更新内容后触发，适合做同步、重新分析或生成衍生数据。",
            system_value="content.updated",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_id", "description": "内容 ID"},
                {"field": "slug", "description": "内容 slug"},
                {"field": "title", "description": "标题"},
                {"field": "changed_fields", "description": "本次变更字段"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.deleted",
            label="内容被删除时",
            description="后台删除内容后触发，适合做同步清理、索引清理或审计记录。",
            system_value="content.deleted",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_id", "description": "内容 ID"},
                {"field": "slug", "description": "内容 slug"},
                {"field": "title", "description": "标题"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.bulk_deleted",
            label="内容被批量删除时",
            description="批量删除内容后触发，适合做批量同步、索引清理或审计记录。",
            system_value="content.bulk_deleted",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "item_ids", "description": "受影响内容 ID 列表"},
                {"field": "affected", "description": "实际影响数量"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.status_changed",
            label="内容状态批量变更时",
            description="批量改状态后触发，适合做发布、归档、同步等后续流程。",
            system_value="content.status_changed",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "item_ids", "description": "受影响内容 ID 列表"},
                {"field": "status", "description": "目标状态"},
                {"field": "visibility", "description": "目标可见性"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.published",
            label="内容发布时",
            description="内容发布到公开状态时触发，适合做通知、外部同步、索引或推送。",
            system_value="content.published",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_id", "description": "内容 ID"},
                {"field": "slug", "description": "内容 slug"},
                {"field": "title", "description": "标题"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.archived",
            label="内容归档时",
            description="内容进入归档状态时触发，适合做收尾、下线同步或提醒。",
            system_value="content.archived",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_id", "description": "内容 ID"},
                {"field": "slug", "description": "内容 slug"},
                {"field": "title", "description": "标题"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="content.visibility_changed",
            label="内容可见性变化时",
            description="内容公开/私有切换后触发，适合做同步或权限类流程。",
            system_value="content.visibility_changed",
            target_types=["content"],
            payload_fields=[
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_id", "description": "内容 ID"},
                {"field": "slug", "description": "内容 slug"},
                {"field": "visibility", "description": "当前可见性"},
            ],
            group_key="content",
            group_label="内容",
        ),
        AgentWorkflowCatalogOptionRead(
            value="subscription.config_updated",
            label="订阅配置更新时",
            description="订阅系统配置变化后触发，适合做通知、联调或配置校验。",
            system_value="subscription.config_updated",
            target_types=["subscription"],
            payload_fields=[
                {"field": "changed_fields", "description": "本次变更字段"},
                {"field": "enabled", "description": "当前是否启用"},
                {"field": "smtp_test_passed", "description": "SMTP 测试是否通过"},
                {"field": "allowed_content_types", "description": "允许订阅的内容类型"},
            ],
            group_key="subscription",
            group_label="订阅",
        ),
        AgentWorkflowCatalogOptionRead(
            value="subscription.created",
            label="新订阅创建时",
            description="用户成功订阅后触发，适合做欢迎流程、同步或打标签。",
            system_value="subscription.created",
            target_types=["subscription"],
            payload_fields=[
                {"field": "email", "description": "订阅邮箱"},
                {"field": "content_types", "description": "订阅内容类型"},
                {"field": "initiator_site_user_id", "description": "发起订阅的站点用户 ID"},
            ],
            group_key="subscription",
            group_label="订阅",
        ),
        AgentWorkflowCatalogOptionRead(
            value="subscription.unsubscribed",
            label="订阅取消时",
            description="用户退订后触发，适合做 CRM 清理、标签更新或分析。",
            system_value="subscription.unsubscribed",
            target_types=["subscription"],
            payload_fields=[{"field": "email", "description": "退订邮箱"}],
            group_key="subscription",
            group_label="订阅",
        ),
        AgentWorkflowCatalogOptionRead(
            value="subscription.notification.sent",
            label="订阅通知发送成功时",
            description="一批订阅通知发送成功后触发，适合做统计、日志或外部同步。",
            system_value="subscription.notification.sent",
            target_types=["subscription_notification"],
            payload_fields=[
                {"field": "notification_id", "description": "通知记录 ID"},
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_slug", "description": "内容 slug"},
                {"field": "recipient_count", "description": "收件人数"},
            ],
            group_key="subscription",
            group_label="订阅",
        ),
        AgentWorkflowCatalogOptionRead(
            value="subscription.notification.failed",
            label="订阅通知发送失败时",
            description="一批订阅通知发送失败后触发，适合做告警、重试或人工介入。",
            system_value="subscription.notification.failed",
            target_types=["subscription_notification"],
            payload_fields=[
                {"field": "notification_id", "description": "通知记录 ID"},
                {"field": "content_type", "description": "内容类型"},
                {"field": "content_slug", "description": "内容 slug"},
                {"field": "recipient_count", "description": "收件人数"},
                {"field": "error", "description": "失败原因"},
            ],
            group_key="subscription",
            group_label="订阅",
        ),
        AgentWorkflowCatalogOptionRead(
            value="backup.config_updated",
            label="备份配置更新时",
            description="备份同步配置变更后触发，适合做提醒、校验或安全联动。",
            system_value="backup.config_updated",
            target_types=["backup_config"],
            payload_fields=[
                {"field": "config_id", "description": "配置 ID"},
                {"field": "enabled", "description": "当前是否启用"},
                {"field": "paused", "description": "当前是否暂停"},
                {"field": "transport_mode", "description": "传输方式"},
                {"field": "interval_minutes", "description": "调度间隔"},
            ],
            group_key="ops",
            group_label="运维",
        ),
        AgentWorkflowCatalogOptionRead(
            value="backup.sync.triggered",
            label="备份同步入队时",
            description="备份任务被安排后触发，适合做通知或记录。",
            system_value="backup.sync.triggered",
            target_types=["backup_sync"],
            payload_fields=[
                {"field": "queue_item_id", "description": "队列项 ID"},
                {"field": "trigger_kind", "description": "触发方式，例如 manual / scheduled"},
                {"field": "transport", "description": "传输方式"},
            ],
            group_key="ops",
            group_label="运维",
        ),
        AgentWorkflowCatalogOptionRead(
            value="backup.sync.started",
            label="备份同步开始时",
            description="备份任务开始执行时触发，适合做状态看板或通知。",
            system_value="backup.sync.started",
            target_types=["backup_sync_run"],
            payload_fields=[
                {"field": "run_id", "description": "运行 ID"},
                {"field": "queue_item_id", "description": "队列项 ID"},
                {"field": "trigger_kind", "description": "触发方式"},
                {"field": "transport", "description": "传输方式"},
            ],
            group_key="ops",
            group_label="运维",
        ),
        AgentWorkflowCatalogOptionRead(
            value="backup.sync.completed",
            label="备份同步完成时",
            description="备份任务成功完成时触发，适合做成功通知或链路收尾。",
            system_value="backup.sync.completed",
            target_types=["backup_sync_run"],
            payload_fields=[
                {"field": "run_id", "description": "运行 ID"},
                {"field": "queue_item_id", "description": "队列项 ID"},
                {"field": "commit_id", "description": "备份提交 ID"},
                {"field": "stats", "description": "本次备份统计信息"},
            ],
            group_key="ops",
            group_label="运维",
        ),
        AgentWorkflowCatalogOptionRead(
            value="backup.sync.failed",
            label="备份同步失败时",
            description="备份任务失败时触发，适合做告警和自动重试策略。",
            system_value="backup.sync.failed",
            target_types=["backup_sync_run"],
            payload_fields=[
                {"field": "run_id", "description": "运行 ID"},
                {"field": "queue_item_id", "description": "队列项 ID"},
                {"field": "error", "description": "失败原因"},
                {"field": "retry_count", "description": "当前重试次数"},
            ],
            group_key="ops",
            group_label="运维",
        ),
        AgentWorkflowCatalogOptionRead(
            value="backup.sync.retried",
            label="备份同步重试时",
            description="备份任务被重新尝试时触发，适合做通知或统计。",
            system_value="backup.sync.retried",
            target_types=["backup_sync_run"],
            payload_fields=[
                {"field": "run_id", "description": "运行 ID"},
                {"field": "queue_item_id", "description": "队列项 ID"},
                {"field": "retry_count", "description": "当前重试次数"},
            ],
            group_key="ops",
            group_label="运维",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.site_checked",
            label="友链站点巡检完成时",
            description="友链站点健康检查完成时触发，适合做监控通知或记录。",
            system_value="friend.site_checked",
            target_types=["friend"],
            payload_fields=[
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "friend_name", "description": "友链名称"},
                {"field": "previous_status", "description": "之前状态"},
                {"field": "status", "description": "当前状态"},
                {"field": "error", "description": "异常信息"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.site_lost",
            label="友链站点失联时",
            description="友链站点从正常变成失联时触发，适合做告警。",
            system_value="friend.site_lost",
            target_types=["friend"],
            payload_fields=[
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "friend_name", "description": "友链名称"},
                {"field": "previous_status", "description": "之前状态"},
                {"field": "status", "description": "当前状态"},
                {"field": "error", "description": "异常信息"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.site_recovered",
            label="友链站点恢复时",
            description="友链站点从失联恢复正常时触发，适合做恢复通知。",
            system_value="friend.site_recovered",
            target_types=["friend"],
            payload_fields=[
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "friend_name", "description": "友链名称"},
                {"field": "previous_status", "description": "之前状态"},
                {"field": "status", "description": "当前状态"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.feed_checked",
            label="友链 RSS 检查完成时",
            description="友链 RSS 源检查完成时触发，适合做抓取统计和提醒。",
            system_value="friend.feed_checked",
            target_types=["friend_feed_source"],
            payload_fields=[
                {"field": "source_id", "description": "RSS 源 ID"},
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "friend_name", "description": "友链名称"},
                {"field": "status", "description": "检查结果状态"},
                {"field": "inserted", "description": "新增条目数"},
                {"field": "feed_url_updated", "description": "RSS 地址是否被更新"},
                {"field": "error", "description": "异常信息"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.feed_error",
            label="友链 RSS 检查失败时",
            description="友链 RSS 源抓取出错时触发，适合做告警或人工复核。",
            system_value="friend.feed_error",
            target_types=["friend_feed_source"],
            payload_fields=[
                {"field": "source_id", "description": "RSS 源 ID"},
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "friend_name", "description": "友链名称"},
                {"field": "error", "description": "异常信息"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.feed_item_discovered",
            label="友链发现新内容时",
            description="友链 RSS 源抓到新条目时触发，适合做同步、推荐或提醒。",
            system_value="friend.feed_item_discovered",
            target_types=["friend_feed_source"],
            payload_fields=[
                {"field": "source_id", "description": "RSS 源 ID"},
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "friend_name", "description": "友链名称"},
                {"field": "inserted", "description": "新增条目数"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.feed_source.created",
            label="友链 RSS 源创建时",
            description="新增 RSS 源后触发，适合做初始化抓取或监控注册。",
            system_value="friend.feed_source.created",
            target_types=["friend_feed_source"],
            payload_fields=[
                {"field": "source_id", "description": "RSS 源 ID"},
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "feed_url", "description": "RSS 地址"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.feed_source.updated",
            label="友链 RSS 源更新时",
            description="RSS 源配置调整后触发，适合做重新抓取或同步。",
            system_value="friend.feed_source.updated",
            target_types=["friend_feed_source"],
            payload_fields=[
                {"field": "source_id", "description": "RSS 源 ID"},
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "feed_url", "description": "RSS 地址"},
                {"field": "changed_fields", "description": "本次变更字段"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="friend.feed_source.deleted",
            label="友链 RSS 源删除时",
            description="RSS 源删除后触发，适合做清理或审计记录。",
            system_value="friend.feed_source.deleted",
            target_types=["friend_feed_source"],
            payload_fields=[
                {"field": "source_id", "description": "RSS 源 ID"},
                {"field": "friend_id", "description": "友链 ID"},
                {"field": "feed_url", "description": "RSS 地址"},
            ],
            group_key="social",
            group_label="友链巡检",
        ),
        AgentWorkflowCatalogOptionRead(
            value="asset.uploaded",
            label="资源上传时",
            description="资源库新增文件后触发，适合做处理、审核、转码或同步。",
            system_value="asset.uploaded",
            target_types=["asset"],
            payload_fields=[
                {"field": "asset_id", "description": "资源 ID"},
                {"field": "resource_key", "description": "资源路径键"},
                {"field": "visibility", "description": "可见性"},
                {"field": "scope", "description": "范围"},
                {"field": "category", "description": "分类"},
                {"field": "file_name", "description": "文件名"},
            ],
            group_key="asset",
            group_label="资源库",
        ),
        AgentWorkflowCatalogOptionRead(
            value="asset.updated",
            label="资源更新时",
            description="资源元数据更新后触发，适合做同步或记录。",
            system_value="asset.updated",
            target_types=["asset"],
            payload_fields=[
                {"field": "asset_id", "description": "资源 ID"},
                {"field": "resource_key", "description": "资源路径键"},
                {"field": "visibility", "description": "可见性"},
                {"field": "scope", "description": "范围"},
                {"field": "category", "description": "分类"},
            ],
            group_key="asset",
            group_label="资源库",
        ),
        AgentWorkflowCatalogOptionRead(
            value="asset.deleted",
            label="资源删除时",
            description="资源删除后触发，适合做外部清理、索引更新或审计。",
            system_value="asset.deleted",
            target_types=["asset"],
            payload_fields=[
                {"field": "asset_id", "description": "资源 ID"},
                {"field": "resource_key", "description": "资源路径键"},
                {"field": "file_name", "description": "文件名"},
            ],
            group_key="asset",
            group_label="资源库",
        ),
        AgentWorkflowCatalogOptionRead(
            value="asset.bulk_deleted",
            label="资源批量删除时",
            description="批量删除资源后触发，适合做批量清理或审计。",
            system_value="asset.bulk_deleted",
            target_types=["asset"],
            payload_fields=[
                {"field": "asset_ids", "description": "资源 ID 列表"},
                {"field": "affected", "description": "实际影响数量"},
            ],
            group_key="asset",
            group_label="资源库",
        ),
        AgentWorkflowCatalogOptionRead(
            value="asset.comment_image_saved",
            label="评论图片保存时",
            description="评论上传图片并保存到资源库后触发，适合做安全扫描或转存。",
            system_value="asset.comment_image_saved",
            target_types=["asset"],
            payload_fields=[
                {"field": "asset_id", "description": "资源 ID"},
                {"field": "resource_key", "description": "资源路径键"},
                {"field": "file_name", "description": "文件名"},
                {"field": "category", "description": "分类，固定为 comment"},
            ],
            group_key="asset",
            group_label="资源库",
        ),
        AgentWorkflowCatalogOptionRead(
            value="site_auth.config_updated",
            label="站点登录配置更新时",
            description="站点登录方式、OAuth 配置或管理员登录方式调整后触发。",
            system_value="site_auth.config_updated",
            target_types=["site_auth_config"],
            payload_fields=[
                {"field": "changed_fields", "description": "本次变更字段"},
                {"field": "visitor_oauth_providers", "description": "前台可用 OAuth 提供商"},
                {"field": "admin_auth_methods", "description": "管理员登录方式"},
                {"field": "email_login_enabled", "description": "前台邮箱登录是否开启"},
                {"field": "admin_email_enabled", "description": "管理员邮箱登录是否开启"},
            ],
            group_key="auth",
            group_label="站点用户",
        ),
        AgentWorkflowCatalogOptionRead(
            value="site_user.session_created",
            label="站点用户登录时",
            description="站点用户会话创建时触发，适合做欢迎流程、审计或登录同步。",
            system_value="site_user.session_created",
            target_types=["site_user"],
            payload_fields=[{"field": "site_user_id", "description": "站点用户 ID"}],
            group_key="auth",
            group_label="站点用户",
        ),
        AgentWorkflowCatalogOptionRead(
            value="site_user.session_deleted",
            label="站点用户退出时",
            description="站点用户会话销毁时触发，适合做清理或审计记录。",
            system_value="site_user.session_deleted",
            target_types=["site_user"],
            payload_fields=[{"field": "site_user_id", "description": "站点用户 ID"}],
            group_key="auth",
            group_label="站点用户",
        ),
        AgentWorkflowCatalogOptionRead(
            value="site_user.profile_updated",
            label="站点用户资料更新时",
            description="站点用户修改昵称或头像后触发，适合做同步和审计。",
            system_value="site_user.profile_updated",
            target_types=["site_user"],
            payload_fields=[
                {"field": "site_user_id", "description": "站点用户 ID"},
                {"field": "display_name", "description": "显示昵称"},
                {"field": "avatar_url", "description": "头像地址"},
            ],
            group_key="auth",
            group_label="站点用户",
        ),
        AgentWorkflowCatalogOptionRead(
            value="site_admin_identity.created",
            label="管理员身份绑定成功时",
            description="站点用户绑定后台管理员权限后触发，适合做审计和通知。",
            system_value="site_admin_identity.created",
            target_types=["site_admin_identity"],
            payload_fields=[
                {"field": "identity_id", "description": "身份绑定 ID"},
                {"field": "site_user_id", "description": "站点用户 ID"},
                {"field": "provider", "description": "绑定方式"},
                {"field": "email", "description": "绑定邮箱"},
            ],
            group_key="auth",
            group_label="站点用户",
        ),
        AgentWorkflowCatalogOptionRead(
            value="site_admin_identity.deleted",
            label="管理员身份解绑时",
            description="后台管理员身份解除绑定后触发，适合做审计和同步清理。",
            system_value="site_admin_identity.deleted",
            target_types=["site_admin_identity"],
            payload_fields=[
                {"field": "identity_id", "description": "身份绑定 ID"},
                {"field": "site_user_id", "description": "站点用户 ID"},
                {"field": "provider", "description": "绑定方式"},
                {"field": "email", "description": "绑定邮箱"},
            ],
            group_key="auth",
            group_label="站点用户",
        ),
        AgentWorkflowCatalogOptionRead(
            value="webhook.test",
            label="Webhook 测试请求时",
            description="管理员测试 Webhook 订阅时触发，主要用于调试和联调。",
            system_value="webhook.test",
            target_types=["webhook"],
            payload_fields=[
                {"field": "message", "description": "测试消息"},
                {"field": "name", "description": "Webhook 名称"},
                {"field": "target_url", "description": "Webhook 目标地址"},
            ],
            group_key="ops",
            group_label="系统",
        ),
    ]


def _legacy_derive_ai_output_schema(
    *,
    node_id: str,
    graph: dict[str, Any],
    operation_catalog: list[Any] | None = None,
) -> dict[str, Any]:
    """Derive an output JSON Schema for an AI task node by inspecting downstream
    edges and their target nodes.

    The schema is assembled from:
    - Downstream operation nodes: their ``input_schema`` tells us which fields
      the AI needs to produce so that argument mappings can resolve correctly.
    - Downstream condition nodes: the expression variables hint at expected
      boolean / string fields.
    - Downstream approval nodes: we know the AI should emit ``needs_approval``,
      ``action``, and ``summary``.

    A ``summary`` field (string, required) and a ``route`` field (string,
    required) are always included so the runtime routing logic works.
    """
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            nodes_by_id[str(node["id"])] = node

    # Build a quick lookup of operation definitions keyed by capability key.
    op_index: dict[str, Any] = {}
    for op in operation_catalog or []:
        key = getattr(op, "key", None) or (op.get("key") if isinstance(op, dict) else None)
        if key:
            op_index[key] = op

    # Collect outgoing target node ids for *this* AI node.
    downstream_node_ids: list[str] = []
    for edge in graph.get("edges") or []:
        if isinstance(edge, dict) and str(edge.get("source") or "") == node_id:
            target = str(edge.get("target") or "").strip()
            if target:
                downstream_node_ids.append(target)

    # Always start with summary + route as baseline.
    properties: dict[str, Any] = {
        "summary": {"type": "string", "description": "Brief human-readable summary of the AI analysis."},
        "route": {"type": "string", "description": "Downstream branch key for routing."},
    }
    required: list[str] = ["summary", "route"]

    for target_id in downstream_node_ids:
        target_node = nodes_by_id.get(target_id)
        if not target_node:
            continue
        target_type = str(target_node.get("type") or "").strip()
        target_config = dict(target_node.get("config") or {})

        # --- Approval nodes expect needs_approval, action, summary ---
        if target_type == "approval.review":
            if "needs_approval" not in properties:
                properties["needs_approval"] = {"type": "boolean", "description": "Whether human approval is needed."}
                required.append("needs_approval")
            if "action" not in properties:
                properties["action"] = {
                    "type": "string",
                    "enum": ["approve", "reject", "pending"],
                    "description": "Proposed moderation or processing action.",
                }
                required.append("action")

        # --- Condition nodes: try to extract referenced variable names ---
        elif target_type == "flow.condition":
            expr = str(target_config.get("expression") or "").strip()
            # Simple heuristic: if the expression references ai_output.X or
            # result.X, treat X as an expected string field.
            for token in ("ai_output.", "result."):
                if token in expr:
                    for part in expr.split(token)[1:]:
                        field_name = ""
                        for ch in part:
                            if ch.isalnum() or ch == "_":
                                field_name += ch
                            else:
                                break
                        if field_name and field_name not in properties:
                            properties[field_name] = {"type": "string"}

        # --- Operation nodes: pull required fields from input_schema ---
        elif target_type.startswith("operation."):
            op_key = str(target_config.get("operation_key") or "").strip()
            op_def = op_index.get(op_key)
            if op_def is not None:
                input_schema = (
                    getattr(op_def, "input_schema", None)
                    if not isinstance(op_def, dict)
                    else op_def.get("input_schema")
                ) or {}
                for prop_name in dict(input_schema.get("properties") or {}):
                    if prop_name not in properties:
                        prop_type = str(
                            dict(input_schema.get("properties") or {}).get(prop_name, {}).get("type", "string")
                        )
                        properties[prop_name] = {"type": prop_type}
            # Also inspect argument_mappings for fields sourced from latest_ai
            for mapping in target_config.get("argument_mappings") or []:
                if not isinstance(mapping, dict):
                    continue
                source = str(mapping.get("source") or "").strip()
                path = str(mapping.get("path") or "").strip()
                if source in ("latest_ai", "artifacts") and path:
                    field_name = path.split(".")[0]
                    if field_name and field_name not in properties:
                        properties[field_name] = {"type": "string"}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def build_workflow_catalog(session: Session, workflow_key: str | None = None) -> AgentWorkflowCatalogRead:
    operations = [
        AgentWorkflowCatalogOperationRead(
            key=item.key,
            operation_type=item.operation_type,
            label=item.label,
            description=item.description,
            group_key=item.group_key,
            group_label=item.group_label,
            risk_level=item.risk_level,
            required_scopes=list(item.required_scopes),
            input_schema=dict(item.input_schema or {}),
            output_schema=dict(item.output_schema or {}),
            invocation=dict(item.invocation or {}),
            examples=list(item.examples or ()),
        )
        for item in list_operation_definitions()
    ]
    templates = [
        AgentWorkflowTemplateRead(
            key=item.key,
            title=item.name,
            description=item.description,
            workflow=item.model_dump(mode="json"),
        )
        for item in list_agent_workflows(session)
        if item.built_in
    ]
    readonly_tools: list[ToolSurfaceRead] = [
        item for item in list_tool_surfaces(None) if not getattr(item, "workflow_local", False)
    ]
    workflow_local_action_surfaces: list[ActionSurfaceRead] = [
        item for item in list_action_surfaces(workflow_key) if getattr(item, "workflow_local", False)
    ]
    return AgentWorkflowCatalogRead(
        node_types=_node_types(),
        trigger_types=_trigger_types(),
        trigger_events=_event_trigger_options(),
        operation_catalog=operations,
        approval_types=_approval_types(),
        expression_catalog=_expression_catalog(),
        template_catalog=templates,
        variable_sources=_variable_sources(),
        readonly_tools=readonly_tools,
        workflow_local_action_surfaces=workflow_local_action_surfaces,
    )


# ---------------------------------------------------------------------------
# AI output schema derivation
# ---------------------------------------------------------------------------
#
# The functions below analyse the graph structure around an ``ai.task`` node
# and derive a unified JSON Schema that the AI model should produce.  The
# schema is inferred by inspecting every *direct* downstream node:
#
#   - operation nodes  -> argument_mappings + operation input_schema
#   - flow.condition   -> expression references to ``ai_output`` fields
#   - approval.review  -> standard summary / needs_approval fields
#
# This keeps the AI output contract in sync with what downstream consumers
# actually need, avoiding manual duplication.
# ---------------------------------------------------------------------------

# Sources recognised as "this value comes from AI output".
_AI_OUTPUT_SOURCES: frozenset[str] = frozenset({"latest_ai", "ai_output", "__auto__"})

# Fields commonly used as condition shortcuts in _condition_environment.
_CONDITION_SHORTCUTS: dict[str, dict[str, Any]] = {
    "needs_approval": {"type": "boolean"},
    "action": {"type": "string"},
    "proposed_action": {"type": "string"},
    "summary": {"type": "string"},
}


def _find_operation_in_catalog(
    operation_key: str,
    catalog: list[AgentWorkflowCatalogOperationRead],
) -> AgentWorkflowCatalogOperationRead | None:
    """Return the operation definition for *operation_key*, or ``None``."""
    for op in catalog:
        if op.key == operation_key:
            return op
    return None


def _collect_from_operation(
    op_def: AgentWorkflowCatalogOperationRead,
    node_config: dict[str, Any],
    properties: dict[str, Any],
    required_fields: list[str],
) -> None:
    """Collect fields that *op_def* needs from the AI output.

    When explicit ``argument_mappings`` exist, only mapped fields whose
    ``source`` is one of :data:`_AI_OUTPUT_SOURCES` are collected.  If no
    mappings are present, all non-ID fields from the operation's
    ``input_schema`` are inferred (auto-mapping).
    """
    mappings = node_config.get("argument_mappings") or []
    op_input_props = (op_def.input_schema or {}).get("properties", {})
    op_required = (op_def.input_schema or {}).get("required", [])

    for mapping in mappings:
        source = mapping.get("source", "")
        if source not in _AI_OUTPUT_SOURCES:
            continue
        path = mapping.get("path") or mapping.get("name", "")
        if not path:
            continue
        # Prefer the operation's own schema definition for this field.
        field_schema = op_input_props.get(mapping.get("name", path), {"type": "string"})
        properties[path] = field_schema
        if mapping.get("name", path) in op_required:
            required_fields.append(path)

    # Auto-mapping: when no explicit mappings exist, infer from the
    # operation input schema (skipping typical context-provided ID fields).
    if not mappings:
        for prop_name, prop_schema in op_input_props.items():
            if prop_name.endswith("_id") or prop_name in ("id",):
                continue
            properties[prop_name] = prop_schema
            if prop_name in op_required:
                required_fields.append(prop_name)


def _collect_from_expression(
    expression: str,
    properties: dict[str, Any],
) -> None:
    """Parse *expression* for AI output field references.

    Recognised patterns:

    * ``path('ai_output.field_name')``
    * ``ai_output["field_name"]`` / ``ai_output['field_name']``
    * Bare shortcut names exposed via ``_condition_environment``
    """
    import re

    # path('ai_output.xxx') or path("ai_output.xxx")
    for match in re.finditer(r"path\(['\"]ai_output\.(\w+)['\"]\)", expression):
        field = match.group(1)
        if field not in properties:
            properties[field] = {"type": "string"}

    # ai_output["xxx"] or ai_output['xxx']
    for match in re.finditer(r"ai_output\[['\"](\w+)['\"]\]", expression):
        field = match.group(1)
        if field not in properties:
            properties[field] = {"type": "string"}

    # Common shortcut variables available in the condition environment.
    for shortcut, schema in _CONDITION_SHORTCUTS.items():
        if shortcut in expression and shortcut not in properties:
            properties[shortcut] = schema


def derive_ai_output_schema(*args: Any, **kwargs: Any):
    """Compatibility wrapper around the workflow compiler's AI schema derivation.

    Supports both call styles currently used across the codebase:

    1. ``derive_ai_output_schema(node_id=..., graph=..., operation_catalog=...)``
    2. ``derive_ai_output_schema(graph_nodes=..., graph_edges=..., ai_node_id=..., operation_catalog=..., node_type_registry=...)``
    """
    if "graph" in kwargs and "node_id" in kwargs:
        graph = dict(kwargs.get("graph") or {})
        graph_nodes = [dict(item) for item in graph.get("nodes") or [] if isinstance(item, dict)]
        graph_edges = [dict(item) for item in graph.get("edges") or [] if isinstance(item, dict)]
        node_type_registry = {item.type: item for item in _node_types()}
        schema, _ = compile_ai_output_schema(
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
            ai_node_id=str(kwargs.get("node_id") or ""),
            operation_catalog=list(kwargs.get("operation_catalog") or []),
            node_type_registry=node_type_registry,
            workflow_key=str(kwargs.get("workflow_key") or "").strip() or None,
        )
        return schema

    schema, source_nodes = compile_ai_output_schema(
        graph_nodes=list(kwargs.get("graph_nodes") or []),
        graph_edges=list(kwargs.get("graph_edges") or []),
        ai_node_id=str(kwargs.get("ai_node_id") or ""),
        operation_catalog=list(kwargs.get("operation_catalog") or []),
        node_type_registry=dict(kwargs.get("node_type_registry") or {}),
        workflow_key=str(kwargs.get("workflow_key") or "").strip() or None,
    )
    return schema, source_nodes
