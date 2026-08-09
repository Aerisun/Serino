from __future__ import annotations

import logging
import threading
from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from aerisun.core.redaction import redact_sensitive_data, restore_redacted_placeholders, sanitize_url
from aerisun.domain.automation import compat
from aerisun.domain.automation.packs import (
    delete_workflow_pack,
    list_workflow_packs,
    load_workflow_pack,
    workflow_from_pack,
    workflow_pack_exists,
    write_workflow_pack,
)
from aerisun.domain.automation.schemas import (
    AgentModelConfigRead,
    AgentModelConfigResolved,
    AgentModelConfigUpdate,
    AgentWorkflowCreate,
    AgentWorkflowGraph,
    AgentWorkflowRead,
    AgentWorkflowRuntimePolicy,
    AgentWorkflowSummaryRead,
    AgentWorkflowTriggerBinding,
    AgentWorkflowUpdate,
    ChatGPTModelConfigRead,
    ChatGPTModelConfigResolved,
    OpenAICompatibleModelConfigRead,
    OpenAICompatibleModelConfigResolved,
)
from aerisun.domain.automation.secrets import decrypt_secret, encrypt_secret
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError
from aerisun.domain.site_config import repository as site_repo

logger = logging.getLogger(__name__)

_feature_flags_lock = threading.Lock()

AGENT_MODEL_CONFIG_FLAG_KEY = "agent_model_config"
AGENT_WORKFLOWS_FLAG_KEY = "agent_workflows"
AGENT_WORKFLOW_DRAFT_FLAG_KEY = "agent_workflow_draft"
AGENT_SURFACE_DRAFTS_FLAG_KEY = "agent_surface_drafts"

WORKFLOW_TEMPLATE_RULES: dict[str, dict[str, str]] = {
    "community_moderation": {"trigger_event": "engagement.pending", "target_type": ""},
    "comment_moderation": {"trigger_event": "comment.pending", "target_type": "comment"},
    "guestbook_moderation": {"trigger_event": "guestbook.pending", "target_type": "guestbook"},
    "content_publish_review": {"trigger_event": "content.publish_requested", "target_type": "content"},
}
WORKFLOW_TEMPLATE_DEFAULT_KEYS: dict[str, str] = {
    "community_moderation": "community_moderation_v1",
    "comment_moderation": "comment_moderation_v1",
    "guestbook_moderation": "guestbook_moderation_v1",
    "content_publish_review": "content_publish_review_v1",
}

LEGACY_NODE_TYPE_ALIASES = compat.LEGACY_NODE_TYPE_ALIASES
LEGACY_TRIGGER_TYPE_ALIASES = compat.LEGACY_TRIGGER_TYPE_ALIASES

DEFAULT_AGENT_MODEL_CONFIG: dict[str, Any] = {
    "schema_version": 2,
    "primary_source": "openai_compatible",
    "chatgpt_oauth": {
        "enabled": False,
        "model": "",
        "timeout_seconds": 60,
    },
    "openai_compatible": {
        "enabled": False,
        "provider": "openai_compatible",
        "base_url": "",
        "model": "",
        "api_key": "",
        "temperature": 0.2,
        "timeout_seconds": 60,
        "advisory_prompt": (
            "You are assisting a website automation workflow for a Chinese content/admin site. "
            "Return strict JSON that matches the requested schema and never wrap it in markdown. "
            "If the event is risky, destructive, or lacks enough context, route the workflow toward approval."
        ),
    },
}


def resolve_workflow_template_key(*, trigger_event: str, target_type: str | None) -> str:
    normalized_event = (trigger_event or "").strip()
    normalized_target = (target_type or "").strip()
    for template_key, rule in WORKFLOW_TEMPLATE_RULES.items():
        if rule["trigger_event"] == normalized_event and rule["target_type"] == normalized_target:
            return template_key
    return "custom"


def workflow_template_rule(template_key: str) -> dict[str, str]:
    return dict(WORKFLOW_TEMPLATE_RULES.get(template_key) or {"trigger_event": "", "target_type": ""})


def default_workflow_key_for_template(template_key: str) -> str:
    return str(WORKFLOW_TEMPLATE_DEFAULT_KEYS.get(template_key) or template_key or "workflow_v2")


def _legacy_default_graph(
    *,
    trigger_event: str,
    target_type: str | None,
    require_human_approval: bool,
    instructions: str,
) -> dict[str, Any]:
    return compat.legacy_default_graph(
        trigger_event=trigger_event,
        target_type=target_type,
        require_human_approval=require_human_approval,
        instructions=instructions,
    )


DEFAULT_AGENT_WORKFLOWS: list[dict[str, Any]] = [
    {
        "schema_version": 2,
        "key": "community_moderation_v1",
        "name": "评论与留言审核",
        "description": "评论和留言统一进入同一个宽松审核流，正常内容直接自动通过。",
        "enabled": True,
        "trigger_bindings": [
            {
                "id": "engagement-trigger",
                "type": "trigger.event",
                "label": "Engagement Pending",
                "enabled": True,
                "config": {
                    "event_type": "engagement.pending",
                    "matched_events": ["engagement.pending", "comment.pending", "guestbook.pending"],
                    "target_type": None,
                },
            }
        ],
        "runtime_policy": {
            "approval_mode": "risk_based",
            "allow_high_risk_without_approval": False,
            "max_steps": 80,
        },
        "graph": _legacy_default_graph(
            trigger_event="engagement.pending",
            target_type=None,
            require_human_approval=False,
            instructions=(
                "这是一个宽松审核流。评论和留言只要不包含辱骂、人身攻击、反党反社会、极端煽动、"
                "明显骚扰或恶意垃圾内容，就应直接 approve。普通吐槽、轻微负面反馈、不同意见、"
                "简短留言和口语化表达默认都应通过。"
            ),
        ),
        "summary": {
            "built_from_template": "community_moderation",
            "narrative": "内置社区审核模板。",
        },
    }
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
    return {str(item.get("key") or "") for item in DEFAULT_AGENT_WORKFLOWS}


def _ensure_builtin_workflow_packs() -> None:
    packs = list_workflow_packs()
    if packs:
        return
    for raw in DEFAULT_AGENT_WORKFLOWS:
        workflow = _workflow_to_read(raw).model_copy(update={"built_in": True})
        write_workflow_pack(workflow=workflow, built_in=True)


def _workflow_to_read(raw: dict[str, Any]) -> AgentWorkflowRead:
    normalized = compat.legacy_to_v2_workflow(raw)
    legacy_fields = compat.derive_legacy_fields(normalized)
    summary = compat.derive_summary(normalized)
    return AgentWorkflowRead.model_validate(
        {
            **normalized,
            "graph": AgentWorkflowGraph.model_validate(normalized["graph"]).model_dump(mode="json"),
            "trigger_bindings": [
                AgentWorkflowTriggerBinding.model_validate(item).model_dump(mode="json")
                for item in normalized["trigger_bindings"]
            ],
            "runtime_policy": AgentWorkflowRuntimePolicy.model_validate(normalized["runtime_policy"]).model_dump(
                mode="json"
            ),
            "summary": summary.model_dump(mode="json"),
            "built_in": str(normalized.get("key") or "") in _workflow_built_in_keys(),
            **legacy_fields,
        }
    )


def _normalized_agent_model_config(raw: object) -> dict[str, Any]:
    data = deepcopy(DEFAULT_AGENT_MODEL_CONFIG)
    if not isinstance(raw, dict):
        return data

    if int(raw.get("schema_version") or 0) >= 2:
        if raw.get("primary_source") in {"chatgpt_oauth", "openai_compatible"}:
            data["primary_source"] = raw["primary_source"]
        for source in ("chatgpt_oauth", "openai_compatible"):
            source_data = raw.get(source)
            if isinstance(source_data, dict):
                data[source].update(source_data)
        return data

    legacy_keys = {
        "enabled",
        "provider",
        "base_url",
        "model",
        "api_key",
        "temperature",
        "timeout_seconds",
        "advisory_prompt",
    }
    data["openai_compatible"].update({key: raw[key] for key in legacy_keys if key in raw})
    return data


def get_agent_model_config_resolved(session: Session) -> AgentModelConfigResolved:
    raw = _feature_flags(session).get(AGENT_MODEL_CONFIG_FLAG_KEY)
    data = _normalized_agent_model_config(raw)
    api_data = dict(data["openai_compatible"])
    api_data["api_key"] = decrypt_secret(str(api_data.get("api_key") or ""), purpose="agent-model-api-key")
    api_config = OpenAICompatibleModelConfigResolved.model_validate(api_data)
    api_config = api_config.model_copy(
        update={
            "is_ready": bool(api_config.base_url.strip() and api_config.model.strip() and api_config.api_key.strip())
        }
    )
    chatgpt_config = ChatGPTModelConfigResolved.model_validate(data["chatgpt_oauth"])
    chatgpt_config = chatgpt_config.model_copy(update={"is_ready": bool(chatgpt_config.model.strip())})
    return AgentModelConfigResolved(
        schema_version=2,
        primary_source=data["primary_source"],
        chatgpt_oauth=chatgpt_config,
        openai_compatible=api_config,
        is_ready=(chatgpt_config.enabled and chatgpt_config.is_ready) or (api_config.enabled and api_config.is_ready),
    )


def agent_model_runtime_config(config: AgentModelConfigResolved) -> dict[str, Any]:
    """Build the secret-bearing, in-memory router config used by model calls."""

    return {
        "schema_version": 2,
        "primary_source": config.primary_source,
        "advisory_prompt": config.openai_compatible.advisory_prompt,
        "chatgpt_oauth": config.chatgpt_oauth.model_dump(exclude={"is_ready"}),
        "openai_compatible": config.openai_compatible.model_dump(exclude={"is_ready"}),
    }


def _public_agent_model_config(
    config: AgentModelConfigResolved,
    *,
    chatgpt_connected: bool = False,
    chatgpt_account_email: str | None = None,
    chatgpt_plan_type: str | None = None,
) -> AgentModelConfigRead:
    api_config = config.openai_compatible
    chatgpt_config = config.chatgpt_oauth
    public_chatgpt = ChatGPTModelConfigRead(
        **chatgpt_config.model_dump(exclude={"is_ready"}),
        connected=chatgpt_connected,
        account_email=chatgpt_account_email,
        plan_type=chatgpt_plan_type,
        is_ready=chatgpt_config.is_ready,
    )
    public_api = OpenAICompatibleModelConfigRead(
        **api_config.model_dump(exclude={"api_key", "is_ready", "base_url"}),
        base_url=sanitize_url(api_config.base_url),
        api_key_configured=bool(api_config.api_key.strip()),
        is_ready=api_config.is_ready,
    )
    return AgentModelConfigRead(
        schema_version=2,
        primary_source=config.primary_source,
        chatgpt_oauth=public_chatgpt,
        openai_compatible=public_api,
        is_ready=(public_chatgpt.enabled and public_chatgpt.is_ready) or (public_api.enabled and public_api.is_ready),
    )


def get_agent_model_config(session: Session) -> AgentModelConfigRead:
    return _public_agent_model_config(get_agent_model_config_resolved(session))


def resolve_agent_model_config(session: Session, payload: AgentModelConfigUpdate) -> AgentModelConfigResolved:
    current = get_agent_model_config_resolved(session)
    next_data: dict[str, Any] = {
        "schema_version": 2,
        "primary_source": payload.primary_source or current.primary_source,
        "chatgpt_oauth": current.chatgpt_oauth.model_dump(exclude={"is_ready"}),
        "openai_compatible": current.openai_compatible.model_dump(exclude={"is_ready"}),
    }

    if payload.chatgpt_oauth is not None:
        next_data["chatgpt_oauth"].update(payload.chatgpt_oauth.model_dump(exclude_unset=True))

    clear_api_key = payload.clear_api_key
    if payload.openai_compatible is not None:
        api_updates = payload.openai_compatible.model_dump(exclude_unset=True, exclude={"clear_api_key"})
        if not str(api_updates.get("api_key") or "").strip():
            api_updates.pop("api_key", None)
        next_data["openai_compatible"].update(api_updates)
        clear_api_key = clear_api_key or payload.openai_compatible.clear_api_key

    legacy_updates = payload.model_dump(
        exclude_unset=True,
        include={
            "enabled",
            "provider",
            "base_url",
            "model",
            "api_key",
            "temperature",
            "timeout_seconds",
            "advisory_prompt",
        },
    )
    if "enabled" not in legacy_updates and any(key in legacy_updates for key in ("base_url", "model", "api_key")):
        legacy_updates["enabled"] = True
    if not str(legacy_updates.get("api_key") or "").strip():
        legacy_updates.pop("api_key", None)
    next_data["openai_compatible"].update(legacy_updates)
    if clear_api_key:
        next_data["openai_compatible"]["api_key"] = ""

    api_config = OpenAICompatibleModelConfigResolved.model_validate(next_data["openai_compatible"])
    api_config = api_config.model_copy(
        update={
            "is_ready": bool(api_config.base_url.strip() and api_config.model.strip() and api_config.api_key.strip())
        }
    )
    chatgpt_config = ChatGPTModelConfigResolved.model_validate(next_data["chatgpt_oauth"])
    chatgpt_config = chatgpt_config.model_copy(update={"is_ready": bool(chatgpt_config.model.strip())})
    if chatgpt_config.enabled:
        from aerisun.domain.outbound_proxy.service import require_outbound_proxy_scope

        require_outbound_proxy_scope(session, scope="oauth")
    return AgentModelConfigResolved(
        schema_version=2,
        primary_source=next_data["primary_source"],
        chatgpt_oauth=chatgpt_config,
        openai_compatible=api_config,
        is_ready=(chatgpt_config.enabled and chatgpt_config.is_ready) or (api_config.enabled and api_config.is_ready),
    )


def update_agent_model_config(session: Session, payload: AgentModelConfigUpdate) -> AgentModelConfigRead:
    config = resolve_agent_model_config(session, payload)
    with _feature_flags_lock:
        profile = _get_site_profile(session)
        feature_flags = dict(profile.feature_flags or {})
        stored_config = {
            "schema_version": 2,
            "primary_source": config.primary_source,
            "chatgpt_oauth": config.chatgpt_oauth.model_dump(exclude={"is_ready"}),
            "openai_compatible": config.openai_compatible.model_dump(exclude={"is_ready"}),
        }
        stored_config["openai_compatible"]["api_key"] = encrypt_secret(
            config.openai_compatible.api_key,
            purpose="agent-model-api-key",
        )
        feature_flags[AGENT_MODEL_CONFIG_FLAG_KEY] = stored_config
        profile.feature_flags = feature_flags
        session.commit()
        session.refresh(profile)
    return get_agent_model_config(session)


def get_surface_draft_payload(session: Session, workflow_key: str) -> dict[str, Any] | None:
    drafts = _feature_flags(session).get(AGENT_SURFACE_DRAFTS_FLAG_KEY)
    if not isinstance(drafts, dict):
        return None
    raw = drafts.get(workflow_key)
    return dict(raw) if isinstance(raw, dict) else None


def save_surface_draft_payload(session: Session, workflow_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _feature_flags_lock:
        profile = _get_site_profile(session)
        feature_flags = dict(profile.feature_flags or {})
        drafts = dict(feature_flags.get(AGENT_SURFACE_DRAFTS_FLAG_KEY) or {})
        drafts[workflow_key] = payload
        feature_flags[AGENT_SURFACE_DRAFTS_FLAG_KEY] = drafts
        profile.feature_flags = feature_flags
        session.commit()
        session.refresh(profile)
        stored = dict(profile.feature_flags.get(AGENT_SURFACE_DRAFTS_FLAG_KEY) or {})
        return dict(stored.get(workflow_key) or {})


def clear_surface_draft_payload(session: Session, workflow_key: str) -> None:
    with _feature_flags_lock:
        profile = _get_site_profile(session)
        feature_flags = dict(profile.feature_flags or {})
        drafts = dict(feature_flags.get(AGENT_SURFACE_DRAFTS_FLAG_KEY) or {})
        drafts.pop(workflow_key, None)
        feature_flags[AGENT_SURFACE_DRAFTS_FLAG_KEY] = drafts
        profile.feature_flags = feature_flags
        session.commit()
        session.refresh(profile)


def get_agent_workflow_draft_payload(session: Session) -> dict[str, Any] | None:
    raw = _feature_flags(session).get(AGENT_WORKFLOW_DRAFT_FLAG_KEY)
    return dict(raw) if isinstance(raw, dict) else None


def save_agent_workflow_draft_payload(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    with _feature_flags_lock:
        profile = _get_site_profile(session)
        feature_flags = dict(profile.feature_flags or {})
        feature_flags[AGENT_WORKFLOW_DRAFT_FLAG_KEY] = payload
        profile.feature_flags = feature_flags
        session.commit()
        session.refresh(profile)
        return dict(profile.feature_flags.get(AGENT_WORKFLOW_DRAFT_FLAG_KEY) or {})


def clear_agent_workflow_draft_payload(session: Session) -> None:
    with _feature_flags_lock:
        profile = _get_site_profile(session)
        feature_flags = dict(profile.feature_flags or {})
        feature_flags.pop(AGENT_WORKFLOW_DRAFT_FLAG_KEY, None)
        profile.feature_flags = feature_flags
        session.commit()
        session.refresh(profile)


def list_agent_workflows(session: Session) -> list[AgentWorkflowRead]:
    _ensure_builtin_workflow_packs()
    workflows: list[AgentWorkflowRead] = []
    for pack in list_workflow_packs():
        try:
            workflows.append(workflow_from_pack(pack))
        except Exception:
            logger.warning("Failed to parse workflow pack: %s", pack.manifest.key, exc_info=True)
    return workflows


def find_agent_workflow(session: Session, workflow_key: str) -> AgentWorkflowRead | None:
    return next((item for item in list_agent_workflows(session) if item.key == workflow_key), None)


def get_agent_workflow(session: Session, workflow_key: str) -> AgentWorkflowRead:
    workflow = find_agent_workflow(session, workflow_key)
    if workflow is None:
        raise ResourceNotFound("Agent workflow not found")
    return workflow


def public_agent_workflow(workflow: AgentWorkflowRead) -> AgentWorkflowRead:
    redacted = redact_sensitive_data(workflow.model_dump(mode="json"))
    return AgentWorkflowRead.model_validate(redacted)


def _payload_to_workflow_dict(
    payload: AgentWorkflowCreate | AgentWorkflowUpdate, *, existing: AgentWorkflowRead | None
) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    base: dict[str, Any] = (
        existing.model_dump(mode="json")
        if existing is not None
        else {
            "schema_version": 2,
            "enabled": True,
            "graph": AgentWorkflowGraph().model_dump(mode="json"),
            "trigger_bindings": [],
            "runtime_policy": AgentWorkflowRuntimePolicy().model_dump(mode="json"),
            "summary": AgentWorkflowSummaryRead().model_dump(mode="json"),
        }
    )
    if existing is not None:
        data = restore_redacted_placeholders(data, base)
    base.update(
        {
            key: value
            for key, value in data.items()
            if key not in {"trigger_event", "target_type", "require_human_approval", "instructions"}
        }
    )

    legacy_trigger_event = str(data.get("trigger_event") or "").strip()
    legacy_target_type = str(data.get("target_type") or "").strip() or None
    legacy_require_approval = data.get("require_human_approval")
    legacy_instructions = str(data.get("instructions") or "").strip()

    if data.get("graph") is not None:
        base["graph"] = compat.normalize_graph_payload(
            AgentWorkflowGraph.model_validate(data["graph"]).model_dump(mode="json")
        )
    elif existing is None and not base.get("graph", {}).get("nodes"):
        trigger_event = legacy_trigger_event or "manual"
        base["graph"] = _legacy_default_graph(
            trigger_event=trigger_event,
            target_type=legacy_target_type,
            require_human_approval=bool(legacy_require_approval),
            instructions=legacy_instructions,
        )
        base["graph"] = compat.normalize_graph_payload(base["graph"])

    if data.get("trigger_bindings") is not None:
        base["trigger_bindings"] = [
            AgentWorkflowTriggerBinding.model_validate(item).model_dump(mode="json")
            for item in data["trigger_bindings"] or []
        ]
    elif existing is None and legacy_trigger_event:
        base["trigger_bindings"] = compat.default_trigger_bindings_from_legacy(
            {
                "trigger_event": legacy_trigger_event,
                "target_type": legacy_target_type,
                "enabled": data.get("enabled", True),
            }
        )

    if data.get("runtime_policy") is not None:
        base["runtime_policy"] = AgentWorkflowRuntimePolicy.model_validate(data["runtime_policy"]).model_dump(
            mode="json"
        )
    else:
        base["runtime_policy"] = compat.normalize_runtime_policy_payload(base.get("runtime_policy"))

    if data.get("summary") is not None and isinstance(data.get("summary"), dict):
        base["summary"] = dict(data["summary"])
    else:
        base["summary"] = dict(base.get("summary") or {})

    if legacy_instructions:
        for node in base.get("graph", {}).get("nodes") or []:
            if str(node.get("type") or "") == "ai.task":
                node.setdefault("config", {})
                node["config"]["instructions"] = legacy_instructions
                break

    if legacy_require_approval is not None:
        for node in base.get("graph", {}).get("nodes") or []:
            if str(node.get("type") or "") == "approval.review":
                node.setdefault("config", {})
                node["config"]["force"] = bool(legacy_require_approval)
                break

    return {
        "schema_version": 2,
        "key": str(base.get("key") or (existing.key if existing else "")),
        "name": str(base.get("name") or (existing.name if existing else "")),
        "description": str(base.get("description") or (existing.description if existing else "")),
        "enabled": bool(base.get("enabled", True)),
        "graph": compat.normalize_graph_payload(base.get("graph")),
        "trigger_bindings": compat.normalize_trigger_bindings_payload(base.get("trigger_bindings")),
        "runtime_policy": compat.normalize_runtime_policy_payload(base.get("runtime_policy")),
        "summary": dict(base.get("summary") or {}),
    }


def create_agent_workflow(session: Session, payload: AgentWorkflowCreate) -> AgentWorkflowRead:
    from aerisun.domain.automation.validation import compile_workflow

    _ensure_builtin_workflow_packs()
    if workflow_pack_exists(payload.key):
        raise StateConflict("Agent workflow key already exists")
    workflow_dict = _payload_to_workflow_dict(payload, existing=None)
    created = AgentWorkflowRead.model_validate(
        {
            **workflow_dict,
            "summary": compat.derive_summary(workflow_dict).model_dump(mode="json"),
            **compat.derive_legacy_fields(workflow_dict),
            "built_in": False,
        }
    )
    compiled = compile_workflow(created.model_dump(mode="json"), session=session)
    if created.enabled and not compiled.ok:
        first_error = next((item for item in compiled.issues if item.level == "error"), None)
        raise ValidationError(first_error.message if first_error is not None else "Workflow validation failed")
    pack = write_workflow_pack(workflow=created, built_in=False)
    return workflow_from_pack(pack)


def update_agent_workflow(
    session: Session,
    *,
    workflow_key: str,
    payload: AgentWorkflowUpdate,
) -> AgentWorkflowRead:
    from aerisun.domain.automation.validation import compile_workflow

    _ensure_builtin_workflow_packs()
    target = find_agent_workflow(session, workflow_key)
    if target is None:
        raise ResourceNotFound("Agent workflow not found")
    workflow_dict = _payload_to_workflow_dict(payload, existing=target)
    updated = AgentWorkflowRead.model_validate(
        {
            **workflow_dict,
            "summary": compat.derive_summary(workflow_dict).model_dump(mode="json"),
            **compat.derive_legacy_fields(workflow_dict),
            "built_in": target.built_in,
        }
    )
    compiled = compile_workflow(updated.model_dump(mode="json"), session=session)
    if updated.enabled and not compiled.ok:
        first_error = next((item for item in compiled.issues if item.level == "error"), None)
        raise ValidationError(first_error.message if first_error is not None else "Workflow validation failed")
    existing_pack = load_workflow_pack(workflow_key)
    saved = write_workflow_pack(
        workflow=updated,
        query_surfaces=list(existing_pack.query_surfaces),
        action_surfaces=list(existing_pack.action_surfaces),
        built_in=existing_pack.manifest.built_in,
    )
    return workflow_from_pack(saved)


def delete_agent_workflow(session: Session, *, workflow_key: str) -> None:
    _ensure_builtin_workflow_packs()
    if not workflow_pack_exists(workflow_key):
        raise ResourceNotFound("Agent workflow not found")
    delete_workflow_pack(workflow_key)


def list_workflows_for_event(
    session: Session,
    *,
    event_type: str,
    target_type: str | None,
) -> list[AgentWorkflowRead]:
    matched: list[AgentWorkflowRead] = []
    normalized_event = (event_type or "").strip()
    normalized_target = (target_type or "").strip()
    for workflow in list_agent_workflows(session):
        if not workflow.enabled:
            continue
        for binding in workflow.trigger_bindings:
            if not binding.enabled or binding.type != "trigger.event":
                continue
            config = dict(binding.config or {})
            matched_events = [str(item).strip() for item in config.get("matched_events") or [] if str(item).strip()]
            binding_event = str(config.get("event_type") or "").strip()
            allowed_target = str(config.get("target_type") or "").strip()
            if normalized_event not in set(matched_events or [binding_event]):
                continue
            if allowed_target and allowed_target != normalized_target:
                continue
            matched.append(workflow)
            break
    return matched


def list_workflow_bindings_by_type(
    session: Session, *, binding_type: str
) -> list[tuple[AgentWorkflowRead, AgentWorkflowTriggerBinding]]:
    results: list[tuple[AgentWorkflowRead, AgentWorkflowTriggerBinding]] = []
    normalized = compat.normalize_binding_type(binding_type)
    for workflow in list_agent_workflows(session):
        if not workflow.enabled:
            continue
        for binding in workflow.trigger_bindings:
            if binding.enabled and binding.type == normalized:
                results.append((workflow, binding))
    return results


def find_workflow_trigger_binding(
    session: Session,
    *,
    workflow_key: str,
    binding_id: str,
) -> tuple[AgentWorkflowRead, AgentWorkflowTriggerBinding]:
    workflow = get_agent_workflow(session, workflow_key)
    for binding in workflow.trigger_bindings:
        if binding.id == binding_id:
            return workflow, binding
    raise ResourceNotFound("Workflow trigger binding not found")
