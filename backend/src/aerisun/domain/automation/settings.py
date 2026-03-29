from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from aerisun.domain.automation.schemas import (
    AgentModelConfigRead,
    AgentModelConfigUpdate,
    AgentWorkflowCreate,
    AgentWorkflowRead,
    AgentWorkflowUpdate,
)
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.site_config import repository as site_repo

AGENT_MODEL_CONFIG_FLAG_KEY = "agent_model_config"
AGENT_WORKFLOWS_FLAG_KEY = "agent_workflows"
AGENT_WORKFLOW_DRAFT_FLAG_KEY = "agent_workflow_draft"

WORKFLOW_TEMPLATE_RULES: dict[str, dict[str, str]] = {
    "community_moderation": {
        "trigger_event": "engagement.pending",
        "target_type": "",
    },
    "comment_moderation": {
        "trigger_event": "comment.pending",
        "target_type": "comment",
    },
    "guestbook_moderation": {
        "trigger_event": "guestbook.pending",
        "target_type": "guestbook",
    },
    "content_publish_review": {
        "trigger_event": "content.publish_requested",
        "target_type": "content",
    },
}
WORKFLOW_TEMPLATE_DEFAULT_KEYS: dict[str, str] = {
    "community_moderation": "community_moderation_v1",
    "comment_moderation": "comment_moderation_v1",
    "guestbook_moderation": "guestbook_moderation_v1",
    "content_publish_review": "content_publish_review_v1",
}

DEFAULT_AGENT_MODEL_CONFIG: dict[str, Any] = {
    "enabled": False,
    "provider": "openai_compatible",
    "base_url": "",
    "model": "",
    "api_key": "",
    "temperature": 0.2,
    "timeout_seconds": 20,
    "advisory_prompt": (
        "You are assisting a website comment and guestbook moderation workflow. "
        "Be lenient by default: approve unless the content contains direct insults, abusive harassment, "
        "anti-social extremist advocacy, violent incitement, or clearly malicious spam. "
        "Return strict JSON with keys summary, needs_approval, and proposed_action. "
        "Use proposed_action='approve' for normal or mildly negative but acceptable messages."
    ),
}

DEFAULT_AGENT_WORKFLOWS: list[dict[str, Any]] = [
    {
        "key": "community_moderation_v1",
        "name": "评论与留言审核",
        "description": "评论和留言统一进入同一个宽松审核流，正常内容直接自动通过。",
        "trigger_event": "engagement.pending",
        "target_type": None,
        "enabled": True,
        "require_human_approval": False,
        "instructions": (
            "这是一个宽松审核流。评论和留言只要不包含辱骂、人身攻击、反党反社会、极端煽动、"
            "明显骚扰或恶意垃圾内容，就应直接 approve。普通吐槽、轻微负面反馈、不同意见、"
            "简短留言和口语化表达默认都应通过。"
        ),
    },
]


def _get_site_profile(session: Session):
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    return profile


def _feature_flags(session: Session) -> dict[str, Any]:
    profile = _get_site_profile(session)
    return dict(profile.feature_flags or {})


def _workflow_built_in_keys() -> set[str]:
    return {item["key"] for item in DEFAULT_AGENT_WORKFLOWS}


LEGACY_COMMUNITY_WORKFLOW_KEYS = {"comment_moderation_v1", "guestbook_moderation_v1"}


def _build_community_workflow_from_legacy(workflows: list[dict[str, Any]]) -> dict[str, Any]:
    legacy_items = [item for item in workflows if str(item.get("key") or "") in LEGACY_COMMUNITY_WORKFLOW_KEYS]
    enabled = any(bool(item.get("enabled", True)) for item in legacy_items) if legacy_items else True
    require_human_approval = (
        any(bool(item.get("require_human_approval", True)) for item in legacy_items) if legacy_items else False
    )
    instructions = "\n\n".join(
        str(item.get("instructions") or "").strip()
        for item in legacy_items
        if str(item.get("instructions") or "").strip()
    )
    return {
        "key": "community_moderation_v1",
        "name": "评论与留言审核",
        "description": "评论和留言统一进入同一个宽松审核流，正常内容直接自动通过。",
        "trigger_event": "engagement.pending",
        "target_type": None,
        "enabled": enabled,
        "require_human_approval": require_human_approval,
        "instructions": instructions or DEFAULT_AGENT_WORKFLOWS[0]["instructions"],
    }


def _normalize_workflow_source(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [dict(item) for item in source if isinstance(item, dict)]
    keys = {str(item.get("key") or "") for item in normalized}
    if "community_moderation_v1" in keys:
        return normalized
    if keys & LEGACY_COMMUNITY_WORKFLOW_KEYS:
        normalized = [item for item in normalized if str(item.get("key") or "") not in LEGACY_COMMUNITY_WORKFLOW_KEYS]
        normalized.insert(0, _build_community_workflow_from_legacy(source))
    return normalized


def resolve_workflow_template_key(*, trigger_event: str, target_type: str | None) -> str:
    normalized_event = (trigger_event or "").strip()
    normalized_target = (target_type or "").strip()
    for template_key, rule in WORKFLOW_TEMPLATE_RULES.items():
        if rule["trigger_event"] == normalized_event and rule["target_type"] == normalized_target:
            return template_key
    raise ValidationError(
        f"Unsupported workflow template for trigger_event={normalized_event!r}, target_type={normalized_target!r}"
    )


def workflow_template_rule(template_key: str) -> dict[str, str]:
    try:
        return dict(WORKFLOW_TEMPLATE_RULES[template_key])
    except KeyError as err:
        raise ValidationError(f"Unsupported workflow template: {template_key}") from err


def default_workflow_key_for_template(template_key: str) -> str:
    try:
        return WORKFLOW_TEMPLATE_DEFAULT_KEYS[template_key]
    except KeyError as err:
        raise ValidationError(f"Unsupported workflow template: {template_key}") from err


def _workflow_to_read(raw: dict[str, Any]) -> AgentWorkflowRead:
    workflow = AgentWorkflowRead.model_validate(raw)
    return workflow.model_copy(update={"built_in": workflow.key in _workflow_built_in_keys()})


def _persist_workflows(session: Session, workflows: list[AgentWorkflowRead]) -> list[AgentWorkflowRead]:
    profile = _get_site_profile(session)
    feature_flags = dict(profile.feature_flags or {})
    feature_flags[AGENT_WORKFLOWS_FLAG_KEY] = [
        {
            "key": workflow.key,
            "name": workflow.name,
            "description": workflow.description,
            "trigger_event": workflow.trigger_event,
            "target_type": workflow.target_type,
            "enabled": workflow.enabled,
            "require_human_approval": workflow.require_human_approval,
            "instructions": workflow.instructions,
        }
        for workflow in workflows
    ]
    profile.feature_flags = feature_flags
    session.commit()
    session.refresh(profile)
    return list_agent_workflows(session)


def get_agent_model_config(session: Session) -> AgentModelConfigRead:
    raw = _feature_flags(session).get(AGENT_MODEL_CONFIG_FLAG_KEY)
    data = dict(DEFAULT_AGENT_MODEL_CONFIG)
    if isinstance(raw, dict):
        data.update(raw)
    config = AgentModelConfigRead.model_validate(data)
    is_ready = bool(config.base_url.strip() and config.model.strip() and config.api_key.strip())
    return config.model_copy(update={"is_ready": is_ready})


def resolve_agent_model_config(session: Session, payload: AgentModelConfigUpdate) -> AgentModelConfigRead:
    current = get_agent_model_config(session)
    next_data = current.model_dump(exclude={"is_ready"})
    next_data.update(payload.model_dump(exclude_unset=True))
    config = AgentModelConfigRead.model_validate(next_data)
    is_ready = bool(config.base_url.strip() and config.model.strip() and config.api_key.strip())
    return config.model_copy(update={"is_ready": is_ready})


def update_agent_model_config(session: Session, payload: AgentModelConfigUpdate) -> AgentModelConfigRead:
    config = resolve_agent_model_config(session, payload)

    profile = _get_site_profile(session)
    feature_flags = dict(profile.feature_flags or {})
    feature_flags[AGENT_MODEL_CONFIG_FLAG_KEY] = config.model_dump(exclude={"is_ready"})
    profile.feature_flags = feature_flags
    session.commit()
    session.refresh(profile)
    return get_agent_model_config(session)


def get_agent_workflow_draft_payload(session: Session) -> dict[str, Any] | None:
    raw = _feature_flags(session).get(AGENT_WORKFLOW_DRAFT_FLAG_KEY)
    return dict(raw) if isinstance(raw, dict) else None


def save_agent_workflow_draft_payload(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    profile = _get_site_profile(session)
    feature_flags = dict(profile.feature_flags or {})
    feature_flags[AGENT_WORKFLOW_DRAFT_FLAG_KEY] = payload
    profile.feature_flags = feature_flags
    session.commit()
    session.refresh(profile)
    return dict(profile.feature_flags.get(AGENT_WORKFLOW_DRAFT_FLAG_KEY) or {})


def clear_agent_workflow_draft_payload(session: Session) -> None:
    profile = _get_site_profile(session)
    feature_flags = dict(profile.feature_flags or {})
    feature_flags.pop(AGENT_WORKFLOW_DRAFT_FLAG_KEY, None)
    profile.feature_flags = feature_flags
    session.commit()
    session.refresh(profile)


def list_agent_workflows(session: Session) -> list[AgentWorkflowRead]:
    raw = _feature_flags(session).get(AGENT_WORKFLOWS_FLAG_KEY)
    source = raw if isinstance(raw, list) and raw else DEFAULT_AGENT_WORKFLOWS
    source = _normalize_workflow_source(source)
    workflows: list[AgentWorkflowRead] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        try:
            workflows.append(_workflow_to_read(item))
        except Exception:
            continue
    if workflows:
        return workflows
    return [_workflow_to_read(item) for item in DEFAULT_AGENT_WORKFLOWS]


def find_agent_workflow(session: Session, workflow_key: str) -> AgentWorkflowRead | None:
    return next((item for item in list_agent_workflows(session) if item.key == workflow_key), None)


def get_agent_workflow(session: Session, workflow_key: str) -> AgentWorkflowRead:
    workflow = find_agent_workflow(session, workflow_key)
    if workflow is None:
        raise ResourceNotFound("Agent workflow not found")
    return workflow


def create_agent_workflow(session: Session, payload: AgentWorkflowCreate) -> AgentWorkflowRead:
    workflows = list_agent_workflows(session)
    if any(item.key == payload.key for item in workflows):
        raise StateConflict("Agent workflow key already exists")
    resolve_workflow_template_key(trigger_event=payload.trigger_event, target_type=payload.target_type)
    workflows.append(
        AgentWorkflowRead(
            key=payload.key,
            name=payload.name,
            description=payload.description,
            trigger_event=payload.trigger_event,
            target_type=payload.target_type,
            enabled=payload.enabled,
            require_human_approval=payload.require_human_approval,
            instructions=payload.instructions,
            built_in=False,
        )
    )
    persisted = _persist_workflows(session, workflows)
    return next(item for item in persisted if item.key == payload.key)


def update_agent_workflow(
    session: Session,
    *,
    workflow_key: str,
    payload: AgentWorkflowUpdate,
) -> AgentWorkflowRead:
    workflows = list_agent_workflows(session)
    target = next((item for item in workflows if item.key == workflow_key), None)
    if target is None:
        raise ResourceNotFound("Agent workflow not found")
    updated = target.model_copy(update=payload.model_dump(exclude_unset=True))
    resolve_workflow_template_key(trigger_event=updated.trigger_event, target_type=updated.target_type)
    persisted = _persist_workflows(
        session,
        [updated if item.key == workflow_key else item for item in workflows],
    )
    return next(item for item in persisted if item.key == workflow_key)


def delete_agent_workflow(session: Session, *, workflow_key: str) -> None:
    workflows = list_agent_workflows(session)
    if not any(item.key == workflow_key for item in workflows):
        raise ResourceNotFound("Agent workflow not found")
    _persist_workflows(session, [item for item in workflows if item.key != workflow_key])


def list_workflows_for_event(
    session: Session,
    *,
    event_type: str,
    target_type: str | None,
) -> list[AgentWorkflowRead]:
    return [
        item
        for item in list_agent_workflows(session)
        if item.enabled
        and (
            item.trigger_event == event_type
            or (item.trigger_event == "engagement.pending" and event_type in {"comment.pending", "guestbook.pending"})
        )
        and (not item.target_type or item.target_type == target_type)
    ]
