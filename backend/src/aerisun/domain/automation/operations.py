from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from aerisun.domain.agent.capabilities.registry import (
    AgentCapabilityDefinition,
    execute_capability,
    get_capability_definition,
    list_capability_definitions,
)


@dataclass(frozen=True, slots=True)
class AutomationOperationDefinition:
    key: str
    operation_type: str
    label: str
    description: str
    group_key: str
    group_label: str
    risk_level: str
    required_scopes: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    invocation: dict[str, Any]
    examples: tuple[dict[str, Any], ...]
    capability_name: str


def _build_operation_definition(
    capability: AgentCapabilityDefinition,
    *,
    operation_type: str,
) -> AutomationOperationDefinition:
    return AutomationOperationDefinition(
        key=capability.name,
        operation_type=operation_type,
        label=capability.label or capability.resolved_label,
        description=capability.description,
        group_key=capability.domain or "misc",
        group_label=capability.group_label or capability.domain or "misc",
        risk_level=capability.risk_level,
        required_scopes=tuple(capability.required_scopes),
        input_schema=dict(capability.input_schema or {}),
        output_schema=dict(capability.output_schema or {}),
        invocation={
            "transport": "capability",
            "tool": capability.name,
            "domain": capability.domain or "misc",
            "intent": capability.intent,
        },
        examples=tuple(capability.examples or ()),
        capability_name=capability.name,
    )


def list_operation_definitions() -> list[AutomationOperationDefinition]:
    operations: list[AutomationOperationDefinition] = []
    for capability in list_capability_definitions(kind="tool"):
        operations.append(_build_operation_definition(capability, operation_type="capability"))
    operations.extend(
        [
            AutomationOperationDefinition(
                key="moderate_comment | moderate_guestbook_entry",
                operation_type="capability",
                label="按对象自动选择评论 / 留言审核",
                description="根据当前对象自动选择评论审核或留言审核。",
                group_key="moderation",
                group_label="审核",
                risk_level="high",
                required_scopes=tuple(),
                input_schema={
                    "type": "object",
                    "properties": {
                        "comment_id": {"type": "string"},
                        "entry_id": {"type": "string"},
                        "action": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
                invocation={"transport": "capability", "tool": "moderate_comment | moderate_guestbook_entry"},
                examples=tuple(),
                capability_name="moderate_comment | moderate_guestbook_entry",
            ),
            AutomationOperationDefinition(
                key="content_publish_review",
                operation_type="capability",
                label="记录内容发布审核结果",
                description="记录发布审核结果，但不会直接改写内容正文。",
                group_key="content",
                group_label="内容",
                risk_level="high",
                required_scopes=tuple(),
                input_schema={
                    "type": "object",
                    "properties": {
                        "content_id": {"type": "string"},
                        "action": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
                output_schema={"type": "object"},
                invocation={"transport": "capability", "tool": "content_publish_review"},
                examples=tuple(),
                capability_name="content_publish_review",
            ),
            AutomationOperationDefinition(
                key="moderation_deferred",
                operation_type="capability",
                label="转人工复核，不直接执行",
                description="保持待处理状态，交给人工复核。",
                group_key="moderation",
                group_label="审核",
                risk_level="low",
                required_scopes=tuple(),
                input_schema={
                    "type": "object",
                    "properties": {"action": {"type": "string"}, "reason": {"type": "string"}},
                },
                output_schema={"type": "object"},
                invocation={"transport": "capability", "tool": "moderation_deferred"},
                examples=tuple(),
                capability_name="moderation_deferred",
            ),
            AutomationOperationDefinition(
                key="noop",
                operation_type="capability",
                label="不执行任何动作",
                description="只保留流程状态，不执行任何副作用。",
                group_key="utility",
                group_label="辅助",
                risk_level="low",
                required_scopes=tuple(),
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
                invocation={"transport": "capability", "tool": "noop"},
                examples=tuple(),
                capability_name="noop",
            ),
        ]
    )
    return operations


_OPERATION_INDEX: dict[tuple[str, str], AutomationOperationDefinition] = {
    (item.operation_type, item.key): item for item in list_operation_definitions()
}


def get_operation_definition(*, operation_type: str, key: str) -> AutomationOperationDefinition:
    normalized_type = (operation_type or "").strip()
    normalized_key = (key or "").strip()
    try:
        return _OPERATION_INDEX[(normalized_type, normalized_key)]
    except KeyError as err:
        raise KeyError(f"Unknown automation operation: {normalized_type}:{normalized_key}") from err


def operation_risk_level(*, operation_type: str, key: str) -> str:
    return get_operation_definition(operation_type=operation_type, key=key).risk_level


def execute_operation(
    session: Session,
    *,
    operation_type: str,
    key: str,
    arguments: dict[str, Any],
) -> Any:
    definition = get_operation_definition(operation_type=operation_type, key=key)
    filtered_arguments = dict(arguments)
    if definition.capability_name == "moderate_comment | moderate_guestbook_entry":
        if str(arguments.get("comment_id") or "").strip():
            capability = get_capability_definition(kind="tool", name="moderate_comment")
            allowed = set(dict(capability.input_schema or {}).get("properties") or {})
            filtered_arguments = {key: value for key, value in arguments.items() if key in allowed}
            return execute_capability(session, kind="tool", name="moderate_comment", **filtered_arguments)
        if str(arguments.get("entry_id") or "").strip():
            capability = get_capability_definition(kind="tool", name="moderate_guestbook_entry")
            allowed = set(dict(capability.input_schema or {}).get("properties") or {})
            filtered_arguments = {key: value for key, value in arguments.items() if key in allowed}
            return execute_capability(session, kind="tool", name="moderate_guestbook_entry", **filtered_arguments)
        raise ValueError("Either comment_id or entry_id is required for combined moderation capability")
    if definition.capability_name == "content_publish_review":
        return {
            "status": "review_recorded",
            "content_id": arguments.get("content_id") or arguments.get("item_id"),
            "action": arguments.get("action"),
            "reason": arguments.get("reason"),
        }
    if definition.capability_name == "moderation_deferred":
        return {"status": "pending", "action": "pending", "reason": arguments.get("reason")}
    if definition.capability_name == "noop":
        return {"status": "noop"}
    capability = get_capability_definition(kind="tool", name=definition.capability_name)
    allowed = set(dict(capability.input_schema or {}).get("properties") or {})
    filtered_arguments = {key: value for key, value in arguments.items() if key in allowed}
    return execute_capability(
        session,
        kind="tool",
        name=capability.name,
        **filtered_arguments,
    )
