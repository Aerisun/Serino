from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.agent.capabilities.registry import list_capability_models
from aerisun.domain.agent.service import build_workflow_planning_usage_context
from aerisun.domain.automation import repository as repo
from aerisun.domain.automation.models import AgentRun, AutomationEvent, WebhookDelivery, WebhookSubscription
from aerisun.domain.automation.runtime import AutomationRuntime, invoke_model_json, probe_model_config
from aerisun.domain.automation.schemas import (
    AgentModelConfigTestRead,
    AgentModelConfigUpdate,
    AgentRunApprovalRead,
    AgentRunRead,
    AgentRunStepRead,
    AgentWorkflowCreate,
    AgentWorkflowDraftChatWrite,
    AgentWorkflowDraftCreateRead,
    AgentWorkflowDraftCreateWrite,
    AgentWorkflowDraftMessageRead,
    AgentWorkflowDraftOptionRead,
    AgentWorkflowDraftQuestionRead,
    AgentWorkflowDraftRead,
    AgentWorkflowRead,
    AgentWorkflowUpdate,
    ApprovalDecisionWrite,
    TelegramWebhookConnectRead,
    WebhookDeadLetterRead,
    WebhookDeliveryRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
    WebhookSubscriptionUpdate,
)
from aerisun.domain.automation.settings import (
    clear_agent_workflow_draft_payload,
    create_agent_workflow,
    default_workflow_key_for_template,
    find_agent_workflow,
    get_agent_model_config,
    get_agent_workflow_draft_payload,
    list_workflows_for_event,
    resolve_agent_model_config,
    resolve_workflow_template_key,
    save_agent_workflow_draft_payload,
    update_agent_workflow,
    workflow_template_rule,
)
from aerisun.domain.exceptions import ResourceNotFound, StateConflict, ValidationError


def enqueue_workflow_run(
    session: Session,
    *,
    workflow_key: str,
    trigger_kind: str,
    trigger_event: str | None,
    target_type: str | None,
    target_id: str | None,
    input_payload: dict[str, Any] | None = None,
    context_payload: dict[str, Any] | None = None,
    autocommit: bool = True,
) -> AgentRunRead:
    run = repo.create_agent_run(
        session,
        workflow_key=workflow_key,
        trigger_kind=trigger_kind,
        trigger_event=trigger_event,
        target_type=target_type,
        target_id=target_id,
        input_payload=input_payload,
        context_payload=context_payload,
        thread_id=__import__("uuid").uuid4().hex,
    )
    if autocommit:
        session.commit()
        session.refresh(run)
    else:
        session.flush()
    return AgentRunRead.model_validate(run)


def _fallback_workflow_config(run: AgentRun) -> AgentWorkflowRead:
    return AgentWorkflowRead(
        key=run.workflow_key,
        name=run.workflow_key,
        description="Workflow configuration is no longer present in admin settings.",
        trigger_event=run.trigger_event or "manual",
        target_type=run.target_type,
        enabled=True,
        require_human_approval=True,
        instructions="",
        built_in=False,
    )


def list_runs(session: Session) -> list[AgentRunRead]:
    return [AgentRunRead.model_validate(item) for item in repo.list_agent_runs(session)]


def get_run_detail(session: Session, run_id: str) -> tuple[AgentRunRead, list[AgentRunStepRead]]:
    run = repo.get_agent_run(session, run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    steps = repo.list_agent_run_steps(session, run_id=run_id)
    return AgentRunRead.model_validate(run), [AgentRunStepRead.model_validate(step) for step in steps]


def list_pending_approvals(session: Session) -> list[AgentRunApprovalRead]:
    return [AgentRunApprovalRead.model_validate(item) for item in repo.list_pending_approvals(session)]


WORKFLOW_DRAFT_ID = "global"
WORKFLOW_DRAFT_MAX_MESSAGES = 20
AI_WORKFLOW_TEMPLATES = ("community_moderation", "content_publish_review")


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _ensure_workflow_ai_model(session: Session) -> dict[str, Any]:
    config = get_agent_model_config(session)
    if not config.enabled:
        raise ValidationError("Agent model is disabled")
    if not config.is_ready:
        raise ValidationError("Agent model config is not ready")
    if config.provider != "openai_compatible":
        raise ValidationError(f"Unsupported model provider: {config.provider}")
    return config.model_dump(exclude={"is_ready"})


def _workflow_template_catalog() -> list[dict[str, Any]]:
    return [
        {
            "template_key": template_key,
            "default_workflow_key": default_workflow_key_for_template(template_key),
            **workflow_template_rule(template_key),
        }
        for template_key in AI_WORKFLOW_TEMPLATES
    ]


def _workflow_capability_catalog() -> list[dict[str, Any]]:
    allowed = {
        "moderate_comment",
        "moderate_guestbook_entry",
        "list_comment_moderation_queue",
        "list_guestbook_moderation_queue",
        "list_admin_content",
        "get_admin_content",
        "update_admin_content",
        "bulk_update_admin_content_status",
    }
    return [
        {
            "id": item.id,
            "name": item.name,
            "kind": item.kind,
            "description": item.description,
            "required_scopes": item.required_scopes,
            "invocation": item.invocation,
            "examples": item.examples,
        }
        for item in list_capability_models(kind="tool")
        if item.name in allowed
    ]


WORKFLOW_TEMPLATE_TOOL_FILTERS: dict[str, set[str]] = {
    "community_moderation": {
        "list_comment_moderation_queue",
        "list_guestbook_moderation_queue",
        "moderate_comment",
        "moderate_guestbook_entry",
    },
    "content_publish_review": {
        "list_admin_content",
        "get_admin_content",
        "update_admin_content",
        "bulk_update_admin_content_status",
    },
}

WORKFLOW_TEMPLATE_PLAYBOOK_FILTERS: dict[str, set[str]] = {
    "community_moderation": set(),
    "content_publish_review": {"list-content", "archive-content"},
}

WORKFLOW_TEMPLATE_MCP_TEMPLATE_FILTERS: dict[str, set[str]] = {
    "community_moderation": {"initialize-list-call"},
    "content_publish_review": {"list-delete-archive"},
}


@lru_cache(maxsize=8)
def _cached_workflow_usage_context(site_url: str) -> dict[str, Any]:
    return dict(build_workflow_planning_usage_context(site_url))


def _workflow_execution_context(*, template_key: str | None, detail_level: str) -> dict[str, Any]:
    site_url = get_settings().site_url
    usage_context = _cached_workflow_usage_context(site_url)
    template_keys = [template_key] if template_key in AI_WORKFLOW_TEMPLATES else list(AI_WORKFLOW_TEMPLATES)

    allowed_tools: set[str] = set()
    allowed_playbooks: set[str] = set()
    allowed_mcp_templates: set[str] = set()
    for key in template_keys:
        allowed_tools.update(WORKFLOW_TEMPLATE_TOOL_FILTERS.get(key, set()))
        allowed_playbooks.update(WORKFLOW_TEMPLATE_PLAYBOOK_FILTERS.get(key, set()))
        allowed_mcp_templates.update(WORKFLOW_TEMPLATE_MCP_TEMPLATE_FILTERS.get(key, set()))

    capabilities = [
        item
        for item in _workflow_capability_catalog()
        if not allowed_tools or str(item.get("name") or "") in allowed_tools
    ]
    endpoints = list(usage_context.get("endpoints") or [])
    if detail_level == "summary":
        return {
            "relevant_capabilities": [
                {
                    "name": item["name"],
                    "description": item["description"],
                    "required_scopes": item["required_scopes"],
                }
                for item in capabilities
            ],
            "endpoints": [
                {
                    "id": item["id"],
                    "method": item["method"],
                    "description": item["description"],
                }
                for item in endpoints
            ],
        }

    playbooks = [
        item
        for item in list(usage_context.get("playbooks") or [])
        if not allowed_playbooks or str(item.get("id") or "") in allowed_playbooks
    ]
    mcp_templates = [
        item
        for item in list(usage_context.get("mcp_templates") or [])
        if not allowed_mcp_templates or str(item.get("id") or "") in allowed_mcp_templates
    ]
    return {
        "relevant_capabilities": capabilities,
        "endpoints": endpoints,
        "playbooks": playbooks,
        "mcp_templates": mcp_templates,
    }


def _draft_from_payload(raw: dict[str, Any] | None) -> AgentWorkflowDraftRead | None:
    if not raw:
        return None
    try:
        return AgentWorkflowDraftRead.model_validate(raw)
    except Exception:
        return None


def get_agent_workflow_draft(session: Session) -> AgentWorkflowDraftRead | None:
    return _draft_from_payload(get_agent_workflow_draft_payload(session))


def _persist_agent_workflow_draft(session: Session, draft: AgentWorkflowDraftRead) -> AgentWorkflowDraftRead:
    payload = save_agent_workflow_draft_payload(session, draft.model_dump(mode="json"))
    stored = _draft_from_payload(payload)
    if stored is None:
        raise ValidationError("Failed to persist workflow draft")
    return stored


def clear_agent_workflow_draft(session: Session) -> None:
    clear_agent_workflow_draft_payload(session)


def _trim_draft_messages(messages: list[AgentWorkflowDraftMessageRead]) -> list[AgentWorkflowDraftMessageRead]:
    return messages[-WORKFLOW_DRAFT_MAX_MESSAGES:]


def _draft_conversation_text(messages: list[AgentWorkflowDraftMessageRead]) -> str:
    return "\n".join(f"{item.role}: {item.content}" for item in messages)


def _normalize_draft_options(raw: Any) -> list[AgentWorkflowDraftOptionRead]:
    if not isinstance(raw, list):
        return []
    options: list[AgentWorkflowDraftOptionRead] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or label).strip()
        if not label or not value:
            continue
        options.append(
            AgentWorkflowDraftOptionRead(
                label=label,
                value=value,
                description=str(item.get("description") or "").strip(),
                requires_input=bool(item.get("requires_input")),
            )
        )
    return options


def _normalize_draft_questions(raw: Any) -> list[AgentWorkflowDraftQuestionRead]:
    if not isinstance(raw, list):
        return []
    questions: list[AgentWorkflowDraftQuestionRead] = []
    for index, item in enumerate(raw[:4], start=1):
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or item.get("question") or "").strip()
        if not prompt:
            continue
        options = _normalize_draft_options(item.get("options"))
        if not options:
            continue
        key = str(item.get("key") or f"q{index}").strip() or f"q{index}"
        questions.append(
            AgentWorkflowDraftQuestionRead(
                key=key,
                prompt=prompt,
                options=options,
            )
        )
    return questions


def _planning_model_config(
    model_config: dict[str, Any],
    *,
    minimum_timeout_seconds: int,
) -> dict[str, Any]:
    next_config = dict(model_config)
    current_timeout = int(float(next_config.get("timeout_seconds") or 20))
    next_config["timeout_seconds"] = max(current_timeout, minimum_timeout_seconds)
    return next_config


def _build_detailed_working_document(
    *,
    model_config: dict[str, Any],
    summary: str,
    conversation_text: str,
    suggested_template: str | None,
) -> str:
    execution_context = _workflow_execution_context(
        template_key=suggested_template,
        detail_level="detailed",
    )
    detailed_plan = invoke_model_json(
        _planning_model_config(model_config, minimum_timeout_seconds=90),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Aerisun workflow planning assistant. "
                    "This is the final plan expansion stage after clarification is complete. "
                    "Return strict JSON only with keys working_document. "
                    "The working_document must be detailed markdown that can be handed directly to the workflow creation executor. "
                    "Write it in a strict plan-mode style with these exact sections in order: Goal, Trigger, Preconditions, "
                    "Decision Matrix, Execution Steps, API/Capability Calls, Failure Handling, Final Workflow Shape. "
                    "In Execution Steps, every step MUST use this five-line template exactly: "
                    "step_id:, action:, capability_or_endpoint:, expected_result:, fallback:. "
                    "In API/Capability Calls, every entry MUST use this five-line template exactly: "
                    "step_id:, action:, capability_or_endpoint:, expected_result:, fallback:. "
                    "Do not collapse multiple actions into one step. "
                    "Use the exact capability names, endpoint ids, playbooks, and MCP templates from this context whenever relevant.\n"
                    f"{json.dumps(execution_context, ensure_ascii=False)}"
                ),
            },
            {
                "role": "user",
                "content": (f"Clarified summary:\n{summary}\n\nConversation transcript:\n{conversation_text}"),
            },
        ],
    )
    return str(detailed_plan.get("working_document") or "").strip()


def _schedule_workflow_draft_plan_enrichment(*, expected_updated_at: str) -> None:
    def run() -> None:
        with get_session_factory()() as session:
            draft = get_agent_workflow_draft(session)
            if draft is None:
                return
            if draft.updated_at.isoformat() != expected_updated_at or draft.status != "finalizing_plan":
                return

            try:
                model_config = _planning_model_config(
                    _ensure_workflow_ai_model(session),
                    minimum_timeout_seconds=90,
                )
                working_document = _build_detailed_working_document(
                    model_config=model_config,
                    summary=draft.summary,
                    conversation_text=_draft_conversation_text(draft.messages),
                    suggested_template=draft.suggested_template,
                )
                latest = get_agent_workflow_draft(session)
                if latest is None:
                    return
                if latest.updated_at.isoformat() != expected_updated_at or latest.status != "finalizing_plan":
                    return
                next_draft = latest.model_copy(
                    update={
                        "status": "ready",
                        "ready_to_create": True,
                        "working_document": working_document or latest.working_document,
                        "updated_at": _now_utc(),
                    }
                )
                _persist_agent_workflow_draft(session, next_draft)
            except Exception:
                latest = get_agent_workflow_draft(session)
                if latest is None:
                    return
                if latest.updated_at.isoformat() != expected_updated_at or latest.status != "finalizing_plan":
                    return
                fallback_draft = latest.model_copy(
                    update={
                        "status": "ready",
                        "ready_to_create": True,
                        "updated_at": _now_utc(),
                    }
                )
                _persist_agent_workflow_draft(session, fallback_draft)

    threading.Thread(target=run, daemon=True).start()


def continue_agent_workflow_draft(
    session: Session,
    payload: AgentWorkflowDraftChatWrite,
    *,
    progress_callback: Callable[[str, dict[str, Any] | None], None] | None = None,
) -> AgentWorkflowDraftRead:
    def emit_progress(status: str, payload: dict[str, Any] | None = None) -> None:
        if progress_callback is not None:
            progress_callback(status, payload)

    emit_progress("loading_draft")
    draft = get_agent_workflow_draft(session)
    now = _now_utc()
    messages = list(draft.messages if draft else [])
    messages.append(AgentWorkflowDraftMessageRead(role="user", content=payload.message.strip(), created_at=now))
    trimmed_messages = _trim_draft_messages(messages)
    model_config = _planning_model_config(
        _ensure_workflow_ai_model(session),
        minimum_timeout_seconds=60,
    )
    draft_template = draft.suggested_template if draft else None
    emit_progress("building_execution_context")
    planning_context = _workflow_execution_context(template_key=draft_template, detail_level="summary")

    emit_progress("invoking_planner_model")
    parsed = invoke_model_json(
        model_config,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Aerisun workflow planning assistant. "
                    "Your job is to clarify the user's workflow requirement through conversation before creation. "
                    "Ask concise but high-signal follow-up questions when important details are missing. "
                    "Prefer collecting multiple independent missing decisions in one round using a structured questionnaire, "
                    "instead of asking only one question at a time. "
                    "This is the lightweight clarification stage. "
                    "If the requirement is clear enough, mark ready_to_create=true and summarize the final plan. "
                    "Supported workflow templates:\n"
                    f"{json.dumps(_workflow_template_catalog(), ensure_ascii=False)}\n\n"
                    "Compact planning context:\n"
                    f"{json.dumps(planning_context, ensure_ascii=False)}\n\n"
                    "Return strict JSON only with keys assistant_message, summary, working_document, "
                    "ready_to_create, suggested_template, questions, current_question, and options. "
                    "questions should be an array of 1 to 4 objects with keys key, prompt, and options. "
                    "Each question should focus on one decision and each option should use label, value, description, and requires_input. "
                    "Use current_question/options only as a compatibility mirror of the first question. "
                    "Only include an Other option when free-form input is actually needed. "
                    "When ready_to_create=false, keep working_document compact and lightweight. "
                    "At most include these short sections: Goal, Missing Decisions, Tentative Trigger, Tentative Capabilities. "
                    "Do not generate the full detailed execution plan in this stage. "
                    "Only mark ready_to_create=true when the key decisions are actually settled. "
                    "Prefer template_key 'community_moderation' for comment/guestbook automation."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Current draft summary:\n"
                    f"{draft.summary if draft else ''}\n\n"
                    "Current working document:\n"
                    f"{draft.working_document if draft else ''}\n\n"
                    "Conversation transcript:\n"
                    f"{_draft_conversation_text(trimmed_messages)}"
                ),
            },
        ],
    )
    emit_progress("processing_model_output")

    assistant_message = str(parsed.get("assistant_message") or "我先整理一下你的工作流需求。").strip()
    fallback_summary = draft.summary if draft else ""
    summary = str(parsed.get("summary") or fallback_summary).strip()
    working_document = str(parsed.get("working_document") or "").strip()
    suggested_template = str(parsed.get("suggested_template") or "").strip() or None
    questions = _normalize_draft_questions(parsed.get("questions"))
    current_question = str(parsed.get("current_question") or assistant_message).strip()
    options = _normalize_draft_options(parsed.get("options"))
    if not questions and current_question and options:
        questions = [
            AgentWorkflowDraftQuestionRead(
                key="q1",
                prompt=current_question,
                options=options,
            )
        ]
    if questions:
        current_question = questions[0].prompt
        options = questions[0].options
    if suggested_template not in AI_WORKFLOW_TEMPLATES:
        suggested_template = draft.suggested_template if draft else None
    ready_to_create = bool(parsed.get("ready_to_create"))
    if ready_to_create:
        questions = []
        current_question = ""
        options = []

    trimmed_messages.append(
        AgentWorkflowDraftMessageRead(role="assistant", content=assistant_message, created_at=_now_utc())
    )

    next_draft = AgentWorkflowDraftRead(
        id=WORKFLOW_DRAFT_ID,
        status="finalizing_plan" if ready_to_create else "active",
        summary=summary,
        ready_to_create=False if ready_to_create else ready_to_create,
        suggested_template=suggested_template,
        questions=questions,
        current_question=current_question,
        options=options,
        working_document=working_document or (draft.working_document if draft else ""),
        messages=_trim_draft_messages(trimmed_messages),
        created_at=draft.created_at if draft else now,
        updated_at=_now_utc(),
    )
    emit_progress("saving_draft")
    persisted = _persist_agent_workflow_draft(session, next_draft)
    if ready_to_create:
        _schedule_workflow_draft_plan_enrichment(expected_updated_at=persisted.updated_at.isoformat())
    return persisted


def create_agent_workflow_from_draft(
    session: Session,
    payload: AgentWorkflowDraftCreateWrite,
) -> AgentWorkflowDraftCreateRead:
    draft = get_agent_workflow_draft(session)
    if draft is None:
        raise ResourceNotFound("Workflow draft not found")
    if not draft.ready_to_create and not payload.force:
        raise ValidationError("Workflow draft is not ready to create yet")

    model_config = _planning_model_config(
        _ensure_workflow_ai_model(session),
        minimum_timeout_seconds=90,
    )
    execution_context = _workflow_execution_context(
        template_key=draft.suggested_template,
        detail_level="detailed",
    )
    parsed = invoke_model_json(
        model_config,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Aerisun workflow execution assistant. "
                    "Convert the clarified workflow draft into one persisted workflow configuration. "
                    "Supported templates:\n"
                    f"{json.dumps(_workflow_template_catalog(), ensure_ascii=False)}\n\n"
                    "Available internal capabilities:\n"
                    f"{json.dumps(_workflow_capability_catalog(), ensure_ascii=False)}\n\n"
                    "Executable endpoint, MCP, and playbook context:\n"
                    f"{json.dumps(execution_context, ensure_ascii=False)}\n\n"
                    "Return strict JSON only with keys summary, analysis, template_key, used_capabilities, and workflow. "
                    "workflow must contain key, name, description, enabled, require_human_approval, and instructions. "
                    "analysis should explain the final execution plan in detail, including trigger timing, decision branches, "
                    "the exact capability or endpoint sequence, and fallback or approval conditions. "
                    "workflow.instructions should be detailed operational instructions, not a short summary. "
                    "Keep the same strict step template in workflow.instructions: each execution item should include "
                    "step_id, action, capability_or_endpoint, expected_result, and fallback. "
                    "Do not invent unsupported trigger events or target types. "
                    "Prefer updating the built-in community_moderation workflow for comment/guestbook review requirements."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Draft summary:\n"
                    f"{draft.summary}\n\n"
                    "Working document:\n"
                    f"{draft.working_document}\n\n"
                    "Conversation transcript:\n"
                    f"{_draft_conversation_text(draft.messages)}"
                ),
            },
        ],
    )

    template_key = str(parsed.get("template_key") or draft.suggested_template or "community_moderation").strip()
    if template_key not in AI_WORKFLOW_TEMPLATES:
        template_key = "community_moderation"
    rule = workflow_template_rule(template_key)
    workflow_payload = dict(parsed.get("workflow") or {})
    default_key = default_workflow_key_for_template(template_key)
    workflow_key = (
        default_key
        if template_key == "community_moderation"
        else str(workflow_payload.get("key") or default_key).strip()
    )
    if not workflow_key:
        workflow_key = default_key

    existing = find_agent_workflow(session, workflow_key)
    workflow_name = (
        str(workflow_payload.get("name") or (existing.name if existing else default_key)).strip() or default_key
    )
    workflow_description = str(
        workflow_payload.get("description") or (existing.description if existing else draft.summary)
    ).strip()
    workflow_instructions = str(
        workflow_payload.get("instructions") or draft.working_document or (existing.instructions if existing else "")
    ).strip()
    require_human_approval = bool(
        workflow_payload.get(
            "require_human_approval",
            existing.require_human_approval if existing else template_key != "community_moderation",
        )
    )
    enabled = bool(workflow_payload.get("enabled", existing.enabled if existing else True))

    if existing is not None:
        workflow = update_agent_workflow(
            session,
            workflow_key=workflow_key,
            payload=AgentWorkflowUpdate(
                name=workflow_name,
                description=workflow_description,
                trigger_event=rule["trigger_event"],
                target_type=rule["target_type"] or None,
                enabled=enabled,
                require_human_approval=require_human_approval,
                instructions=workflow_instructions,
            ),
        )
    else:
        try:
            workflow = create_agent_workflow(
                session,
                AgentWorkflowCreate(
                    key=workflow_key,
                    name=workflow_name,
                    description=workflow_description,
                    trigger_event=rule["trigger_event"],
                    target_type=rule["target_type"] or None,
                    enabled=enabled,
                    require_human_approval=require_human_approval,
                    instructions=workflow_instructions,
                ),
            )
        except StateConflict:
            workflow = update_agent_workflow(
                session,
                workflow_key=workflow_key,
                payload=AgentWorkflowUpdate(
                    name=workflow_name,
                    description=workflow_description,
                    trigger_event=rule["trigger_event"],
                    target_type=rule["target_type"] or None,
                    enabled=enabled,
                    require_human_approval=require_human_approval,
                    instructions=workflow_instructions,
                ),
            )

    clear_agent_workflow_draft(session)
    return AgentWorkflowDraftCreateRead(
        ok=True,
        summary=str(parsed.get("summary") or "Workflow created successfully."),
        draft_cleared=True,
        workflow=workflow,
    )


def list_webhook_subscriptions(session: Session) -> list[WebhookSubscriptionRead]:
    return [WebhookSubscriptionRead.model_validate(item) for item in repo.list_webhook_subscriptions(session)]


def create_webhook_subscription(session: Session, payload: WebhookSubscriptionCreate) -> WebhookSubscriptionRead:
    item = repo.create_webhook_subscription(
        session,
        name=payload.name,
        status=payload.status,
        target_url=payload.target_url,
        secret=payload.secret,
        event_types=payload.event_types,
        timeout_seconds=payload.timeout_seconds,
        max_attempts=payload.max_attempts,
        headers=payload.headers,
    )
    session.commit()
    session.refresh(item)
    return WebhookSubscriptionRead.model_validate(item)


def test_webhook_subscription(
    session: Session,
    payload: WebhookSubscriptionCreate,
    *,
    subscription_id: str | None = None,
) -> dict[str, Any]:
    subscription = WebhookSubscription(
        name=payload.name or "Webhook test",
        status=payload.status,
        target_url=payload.target_url,
        secret=payload.secret,
        event_types=payload.event_types,
        timeout_seconds=payload.timeout_seconds,
        max_attempts=payload.max_attempts,
        headers=payload.headers,
    )
    event = AutomationEvent(
        event_type="webhook.test",
        event_id=uuid4().hex,
        target_type="webhook",
        target_id=subscription.name,
        payload={
            "message": "Aerisun webhook test",
            "name": subscription.name,
            "target_url": subscription.target_url,
        },
    )
    target_url, request_payload, headers = _build_webhook_request(subscription, event)
    timeout = httpx.Timeout(float(subscription.timeout_seconds or 10))
    try:
        response = httpx.post(target_url, json=request_payload, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        result = {
            "ok": False,
            "provider": _detect_webhook_provider(target_url),
            "target_url": target_url,
            "status_code": None,
            "summary": str(exc),
            "response_body": None,
        }
        _save_webhook_test_result(
            session,
            subscription_id=subscription_id,
            ok=False,
            summary=result["summary"],
        )
        return result

    ok = response.status_code < 400
    summary = "Webhook test succeeded" if ok else f"Webhook returned HTTP {response.status_code}"
    result = {
        "ok": ok,
        "provider": _detect_webhook_provider(target_url),
        "target_url": target_url,
        "status_code": response.status_code,
        "summary": summary,
        "response_body": response.text[:2000],
    }
    _save_webhook_test_result(
        session,
        subscription_id=subscription_id,
        ok=ok,
        summary=summary,
    )
    return result


def _save_webhook_test_result(
    session: Session,
    *,
    subscription_id: str | None,
    ok: bool,
    summary: str,
) -> None:
    if not subscription_id:
        return

    subscription = repo.get_webhook_subscription(session, subscription_id)
    if subscription is None:
        raise ResourceNotFound("Webhook subscription not found")

    subscription.last_test_status = "succeeded" if ok else "failed"
    subscription.last_test_error = None if ok else summary
    subscription.last_tested_at = datetime.now(UTC)
    session.commit()


def connect_telegram_webhook(
    *,
    bot_token: str,
    send_test_message: bool = True,
) -> TelegramWebhookConnectRead:
    token = str(bot_token or "").strip()
    if not token:
        raise ValidationError("bot_token is required")

    base_url = f"https://api.telegram.org/bot{token}"
    timeout = httpx.Timeout(connect=20.0, read=20.0, write=20.0, pool=20.0)

    me_response, me_error = _telegram_request_with_retry(
        "GET",
        f"{base_url}/getMe",
        timeout=timeout,
    )
    if me_response is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="network_error",
            summary=f"Failed to reach Telegram: {me_error}",
        )
    me_payload = _safe_json_response(me_response)

    if me_response.status_code >= 400 or not me_payload.get("ok"):
        detail = str(me_payload.get("description") or f"HTTP {me_response.status_code}")
        return TelegramWebhookConnectRead(
            ok=False,
            status="invalid_token",
            summary=f"Bot token validation failed: {detail}",
        )

    username = str((me_payload.get("result") or {}).get("username") or "") or None

    delete_response, delete_error = _telegram_request_with_retry(
        "GET",
        f"{base_url}/deleteWebhook",
        params={"drop_pending_updates": "false"},
        timeout=timeout,
    )
    if delete_response is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="network_error",
            bot_username=username,
            summary=f"Failed to disable webhook mode: {delete_error}",
        )
    delete_payload = _safe_json_response(delete_response)

    if delete_response.status_code >= 400 or not delete_payload.get("ok"):
        detail = str(delete_payload.get("description") or f"HTTP {delete_response.status_code}")
        return TelegramWebhookConnectRead(
            ok=False,
            status="delete_webhook_failed",
            bot_username=username,
            summary=f"Could not switch to getUpdates mode: {detail}",
        )

    # Read only the latest update and discard older backlog entries.
    # This avoids reconnect failures caused by stale chat history from previous bot setups.
    updates_response, updates_error = _telegram_request_with_retry(
        "GET",
        f"{base_url}/getUpdates",
        params={"offset": -1, "limit": 1, "timeout": 0},
        timeout=timeout,
    )
    if updates_response is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="network_error",
            bot_username=username,
            summary=f"Failed to read updates: {updates_error}",
        )
    updates_payload = _safe_json_response(updates_response)

    if updates_response.status_code >= 400 or not updates_payload.get("ok"):
        detail = str(updates_payload.get("description") or f"HTTP {updates_response.status_code}")
        return TelegramWebhookConnectRead(
            ok=False,
            status="get_updates_failed",
            bot_username=username,
            summary=f"Telegram getUpdates failed: {detail}",
        )

    updates = updates_payload.get("result") if isinstance(updates_payload.get("result"), list) else []
    chat_id = _extract_telegram_chat_id(updates)

    if chat_id is None:
        # If no latest update is available, briefly poll for a fresh message after clearing backlog.
        wait_response, wait_error = _telegram_request_with_retry(
            "GET",
            f"{base_url}/getUpdates",
            params={"limit": 1, "timeout": 8},
            timeout=timeout,
            attempts=2,
        )
        if wait_response is None:
            return TelegramWebhookConnectRead(
                ok=False,
                status="network_error",
                bot_username=username,
                summary=f"Failed while waiting for a new chat message: {wait_error}",
            )
        wait_payload = _safe_json_response(wait_response)

        if wait_response.status_code >= 400 or not wait_payload.get("ok"):
            detail = str(wait_payload.get("description") or f"HTTP {wait_response.status_code}")
            return TelegramWebhookConnectRead(
                ok=False,
                status="get_updates_failed",
                bot_username=username,
                summary=f"Telegram getUpdates failed: {detail}",
            )

        wait_updates = wait_payload.get("result") if isinstance(wait_payload.get("result"), list) else []
        chat_id = _extract_telegram_chat_id(wait_updates)

    if chat_id is None:
        return TelegramWebhookConnectRead(
            ok=False,
            status="awaiting_message",
            bot_username=username,
            summary="No recent chat found. Send a message to the bot, then retry connect.",
        )

    target_url = f"{base_url}/sendMessage?chat_id={chat_id}"

    if send_test_message:
        send_response, send_error = _telegram_request_with_retry(
            "POST",
            f"{base_url}/sendMessage",
            json_payload={
                "chat_id": chat_id,
                "text": "Aerisun Telegram connection successful. chat_id is ready.",
            },
            timeout=timeout,
        )
        if send_response is None:
            return TelegramWebhookConnectRead(
                ok=False,
                status="network_error",
                bot_username=username,
                chat_id=chat_id,
                target_url=target_url,
                summary=f"Could not send verification message: {send_error}",
            )
        send_payload = _safe_json_response(send_response)

        if send_response.status_code >= 400 or not send_payload.get("ok"):
            detail = str(send_payload.get("description") or f"HTTP {send_response.status_code}")
            return TelegramWebhookConnectRead(
                ok=False,
                status="send_test_failed",
                bot_username=username,
                chat_id=chat_id,
                target_url=target_url,
                summary=f"chat_id found but sendMessage failed: {detail}",
            )

    return TelegramWebhookConnectRead(
        ok=True,
        status="connected",
        bot_username=username,
        chat_id=chat_id,
        target_url=target_url,
        summary="Telegram is connected. chat_id has been detected and verified.",
    )


def update_webhook_subscription(
    session: Session,
    *,
    subscription_id: str,
    payload: WebhookSubscriptionUpdate,
) -> WebhookSubscriptionRead:
    item = repo.get_webhook_subscription(session, subscription_id)
    if item is None:
        raise ResourceNotFound("Webhook subscription not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)
    session.commit()
    session.refresh(item)
    return WebhookSubscriptionRead.model_validate(item)


def delete_webhook_subscription(session: Session, *, subscription_id: str) -> None:
    item = repo.get_webhook_subscription(session, subscription_id)
    if item is None:
        raise ResourceNotFound("Webhook subscription not found")
    repo.delete_webhook_subscription(session, item)
    session.commit()


def list_webhook_deliveries(session: Session) -> list[WebhookDeliveryRead]:
    return [WebhookDeliveryRead.model_validate(item) for item in repo.list_webhook_deliveries(session)]


def list_webhook_dead_letters(session: Session) -> list[WebhookDeadLetterRead]:
    return [WebhookDeadLetterRead.model_validate(item) for item in repo.list_webhook_dead_letters(session)]


def _model_chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _format_model_config_test_failure(message: str) -> str:
    detail = message.strip() or "Model endpoint test failed."
    guidance = "请检查 Base URL 是否为 OpenAI 兼容 API 根地址（通常包含 /v1），并确认 API Key 正确且有权限。"
    if "请检查 Base URL" in detail:
        return detail
    return f"{detail} {guidance}"


def test_agent_model_config(session: Session, payload: AgentModelConfigUpdate) -> AgentModelConfigTestRead:
    config = resolve_agent_model_config(session, payload)
    endpoint = _model_chat_completions_url(str(config.base_url or ""))
    try:
        probe = probe_model_config(config.model_dump(exclude={"is_ready"}))
        return AgentModelConfigTestRead(
            ok=True, model=probe["model"], endpoint=probe["endpoint"], summary=probe["summary"]
        )
    except Exception as exc:
        return AgentModelConfigTestRead(
            ok=False,
            model=str(config.model or ""),
            endpoint=endpoint,
            summary=_format_model_config_test_failure(str(exc)),
        )


def replay_dead_letter(session: Session, *, dead_letter_id: str) -> WebhookDeliveryRead:
    dead_letter = repo.get_webhook_dead_letter(session, dead_letter_id)
    if dead_letter is None:
        raise ResourceNotFound("Webhook dead letter not found")
    subscription = repo.get_webhook_subscription(session, dead_letter.subscription_id)
    if subscription is None:
        raise ResourceNotFound("Webhook subscription not found")
    delivery = repo.create_webhook_delivery(
        session,
        subscription=subscription,
        event=AutomationEvent(
            event_type=dead_letter.event_type,
            event_id=dead_letter.event_id,
            target_type=str(dead_letter.payload.get("target_type") or "unknown"),
            target_id=str(dead_letter.payload.get("target_id") or "unknown"),
            payload=dict(dead_letter.payload),
        ),
    )
    repo.delete_webhook_dead_letter(session, dead_letter)
    session.commit()
    session.refresh(delivery)
    return WebhookDeliveryRead.model_validate(delivery)


def trigger_delivery_retry(session: Session, *, delivery_id: str) -> WebhookDeliveryRead:
    delivery = repo.get_webhook_delivery(session, delivery_id)
    if delivery is None:
        raise ResourceNotFound("Webhook delivery not found")
    delivery.status = "pending"
    delivery.next_attempt_at = datetime.now(UTC)
    session.commit()
    session.refresh(delivery)
    return WebhookDeliveryRead.model_validate(delivery)


def _mark_run_cancelled(
    session: Session,
    *,
    run: AgentRun,
    sequence_no: int,
    narrative: str,
    reason: str,
) -> None:
    run.status = "cancelled"
    run.finished_at = datetime.now(UTC)
    run.result_payload = {"skipped": True, "reason": reason, "workflow_key": run.workflow_key}
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=sequence_no,
        node_key="workflow_dispatch",
        step_kind="node_cancelled",
        status="cancelled",
        narrative=narrative,
        output_payload=run.result_payload,
        finished_at=datetime.now(UTC),
    )


def _mark_run_failed(
    session: Session,
    *,
    run: AgentRun,
    sequence_no: int,
    narrative: str,
    error_code: str,
    error_message: str,
) -> None:
    run.status = "failed"
    run.finished_at = datetime.now(UTC)
    run.error_code = error_code
    run.error_message = error_message
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=sequence_no,
        node_key="workflow_dispatch",
        step_kind="node_failed",
        status="failed",
        narrative=narrative,
        error_payload={"error_code": run.error_code, "error_message": run.error_message},
        finished_at=datetime.now(UTC),
    )


def _extract_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result_payload")
    return payload if isinstance(payload, dict) else result


def execute_due_runs(session: Session, runtime: AutomationRuntime) -> int:
    runs = [item for item in repo.list_agent_runs(session, limit=20) if item.status == "queued"]
    processed = 0
    for run in runs:
        processed += 1
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        session.commit()
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=1,
            node_key="workflow_dispatch",
            step_kind="node_entered",
            status="running",
            narrative=f"开始执行工作流 {run.workflow_key}。",
            input_payload=run.input_payload,
            started_at=datetime.now(UTC),
        )
        session.commit()
        workflow_config = find_agent_workflow(session, run.workflow_key) or _fallback_workflow_config(run)
        model_config = get_agent_model_config(session)
        try:
            workflow_template = resolve_workflow_template_key(
                trigger_event=workflow_config.trigger_event,
                target_type=workflow_config.target_type,
            )
        except ValidationError as exc:
            _mark_run_failed(
                session,
                run=run,
                sequence_no=2,
                narrative="工作流模板配置无效。",
                error_code=exc.__class__.__name__,
                error_message=str(exc),
            )
            session.commit()
            continue
        if not model_config.enabled:
            _mark_run_cancelled(
                session,
                run=run,
                sequence_no=2,
                narrative="Agent 模型开关已关闭，当前工作流不执行。",
                reason="model_disabled",
            )
            session.commit()
            continue
        if not model_config.is_ready:
            _mark_run_failed(
                session,
                run=run,
                sequence_no=2,
                narrative="Agent 模型配置不完整，无法执行工作流。",
                error_code="ModelConfigNotReady",
                error_message="Agent model config is not ready",
            )
            session.commit()
            continue
        if model_config.provider != "openai_compatible":
            _mark_run_failed(
                session,
                run=run,
                sequence_no=2,
                narrative="当前 Agent 模型服务商尚未接入执行链路。",
                error_code="UnsupportedModelProvider",
                error_message=f"Unsupported model provider: {model_config.provider}",
            )
            session.commit()
            continue
        try:
            result = runtime.invoke(
                {
                    "run_id": run.id,
                    "workflow_key": run.workflow_key,
                    "workflow_template": workflow_template,
                    "target_type": run.target_type,
                    "target_id": run.target_id,
                    "trigger_event": run.trigger_event,
                    "context_payload": run.context_payload,
                    "workflow_config": workflow_config.model_dump(),
                    "model_config": model_config.model_dump(),
                },
                thread_id=run.thread_id,
            )
            snapshot = runtime.get_state(thread_id=run.thread_id)
            run.latest_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
            run.checkpoint_ns = snapshot.config.get("configurable", {}).get("checkpoint_ns")
            interrupts = result.get("__interrupt__") or []
            if interrupts:
                run.status = "awaiting_approval"
                repo.add_agent_run_step(
                    session,
                    run_id=run.id,
                    sequence_no=2,
                    node_key="request_approval",
                    step_kind="interrupt_requested",
                    status="interrupted",
                    narrative="工作流请求人工审批。",
                    output_payload={"interrupt_count": len(interrupts)},
                    finished_at=datetime.now(UTC),
                )
                first = interrupts[0]
                interrupt_id = getattr(first, "id", None) or f"{run.id}:approval"
                request_payload = {"value": getattr(first, "value", None)}
                repo.create_agent_run_approval(
                    session,
                    run_id=run.id,
                    step_id=None,
                    interrupt_id=interrupt_id,
                    node_key="request_approval",
                    approval_type="moderation_decision",
                    request_payload=request_payload,
                )
            else:
                run.status = "completed"
                run.finished_at = datetime.now(UTC)
                run.result_payload = _extract_result_payload(result)
                repo.add_agent_run_step(
                    session,
                    run_id=run.id,
                    sequence_no=2,
                    node_key="apply_decision",
                    step_kind="node_completed",
                    status="completed",
                    narrative="工作流已完成。",
                    output_payload=run.result_payload,
                    finished_at=datetime.now(UTC),
                )
        except Exception as exc:
            _mark_run_failed(
                session,
                run=run,
                sequence_no=2,
                narrative="工作流执行失败。",
                error_code=exc.__class__.__name__,
                error_message=str(exc),
            )
        session.commit()
    return processed


def resolve_approval(
    session: Session,
    runtime: AutomationRuntime,
    *,
    approval_id: str,
    actor_id: str,
    decision_payload: ApprovalDecisionWrite | dict[str, Any],
) -> AgentRunRead:
    if isinstance(decision_payload, ApprovalDecisionWrite):
        decision_payload = decision_payload.model_dump(exclude_none=True)
    approval = repo.get_approval(session, approval_id)
    if approval is None:
        raise ResourceNotFound("Approval not found")
    run = repo.get_agent_run(session, approval.run_id)
    if run is None:
        raise ResourceNotFound("Agent run not found")
    approval.status = "approved" if (decision_payload.get("action") or "approve") != "reject" else "rejected"
    approval.response_payload = decision_payload
    approval.resolved_by_type = "admin"
    approval.resolved_by_id = actor_id
    approval.resolved_at = datetime.now(UTC)
    repo.add_agent_run_step(
        session,
        run_id=run.id,
        sequence_no=len(repo.list_agent_run_steps(session, run_id=run.id)) + 1,
        node_key="request_approval",
        step_kind="resume_requested",
        status="running",
        narrative="管理员已提交审批结果，准备恢复工作流。",
        input_payload=decision_payload,
        started_at=datetime.now(UTC),
    )
    session.commit()

    try:
        result = runtime.resume(thread_id=run.thread_id, resume_value=decision_payload)
        snapshot = runtime.get_state(thread_id=run.thread_id)
        run.latest_checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
        run.checkpoint_ns = snapshot.config.get("configurable", {}).get("checkpoint_ns")
        run.result_payload = _extract_result_payload(result)
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        repo.add_agent_run_step(
            session,
            run_id=run.id,
            sequence_no=len(repo.list_agent_run_steps(session, run_id=run.id)) + 1,
            node_key="apply_decision",
            step_kind="node_completed",
            status="completed",
            narrative="审批结果已应用，工作流完成。",
            output_payload=run.result_payload,
            finished_at=datetime.now(UTC),
        )
    except Exception as exc:
        _mark_run_failed(
            session,
            run=run,
            sequence_no=len(repo.list_agent_run_steps(session, run_id=run.id)) + 1,
            narrative="审批恢复后执行失败。",
            error_code=exc.__class__.__name__,
            error_message=str(exc),
        )
    session.commit()
    session.refresh(run)
    return AgentRunRead.model_validate(run)


def emit_event(session: Session, event: AutomationEvent) -> None:
    subscriptions = repo.list_active_webhook_subscriptions(session, event_type=event.event_type)
    for subscription in subscriptions:
        if subscription.event_types and event.event_type not in subscription.event_types:
            continue
        repo.create_webhook_delivery(session, subscription=subscription, event=event)
    workflows = list_workflows_for_event(
        session,
        event_type=event.event_type,
        target_type=event.target_type,
    )
    for workflow in workflows:
        enqueue_workflow_run(
            session,
            workflow_key=workflow.key,
            trigger_kind="event",
            trigger_event=event.event_type,
            target_type=event.target_type,
            target_id=event.target_id,
            input_payload={"event_id": event.event_id},
            context_payload=event.payload,
            autocommit=False,
        )
    session.commit()


def dispatch_due_webhooks(session: Session) -> int:
    now = datetime.now(UTC)
    deliveries = repo.list_due_webhook_deliveries(session, now=now)
    processed = 0
    for delivery in deliveries:
        processed += 1
        _deliver_once(session, delivery, now=now)
    return processed


def _deliver_once(session: Session, delivery: WebhookDelivery, *, now: datetime) -> None:
    subscription = repo.get_webhook_subscription(session, delivery.subscription_id)
    if subscription is None:
        delivery.status = "dead_lettered"
        delivery.last_error = "Webhook subscription not found"
        session.commit()
        return

    try:
        target_url, payload, headers = _build_webhook_request(subscription, delivery)
    except (TypeError, ValidationError) as exc:
        delivery.status = "dead_lettered"
        delivery.last_error = str(exc)
        repo.create_dead_letter(session, delivery=delivery, reason="invalid_webhook_request")
        session.commit()
        return

    delivery.status = "delivering"
    delivery.last_attempt_at = now
    delivery.attempt_count += 1
    session.commit()
    timeout = httpx.Timeout(10.0)
    try:
        response = httpx.post(target_url, json=payload, headers=headers, timeout=timeout)
        delivery.last_response_status = response.status_code
        delivery.last_response_body = response.text[:2000]
        if response.status_code < 400:
            delivery.status = "succeeded"
            delivery.delivered_at = datetime.now(UTC)
        elif response.status_code in {408, 409, 429} or response.status_code >= 500:
            _schedule_retry_or_dead_letter(
                session,
                delivery,
                max_attempts=subscription.max_attempts,
                reason=f"http_{response.status_code}",
            )
            return
        else:
            delivery.status = "dead_lettered"
            delivery.last_error = f"Non-retryable HTTP {response.status_code}"
            repo.create_dead_letter(session, delivery=delivery, reason=f"http_{response.status_code}")
        session.commit()
    except httpx.HTTPError as exc:
        delivery.last_error = str(exc)
        _schedule_retry_or_dead_letter(
            session,
            delivery,
            max_attempts=subscription.max_attempts,
            reason="network_error",
        )


def _schedule_retry_or_dead_letter(
    session: Session,
    delivery: WebhookDelivery,
    *,
    max_attempts: int,
    reason: str,
) -> None:
    if delivery.attempt_count >= max_attempts:
        delivery.status = "dead_lettered"
        repo.create_dead_letter(session, delivery=delivery, reason=reason)
        session.commit()
        return
    backoff = min(30 * (4 ** max(delivery.attempt_count - 1, 0)), 7200)
    delivery.status = "retry_scheduled"
    delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
    session.commit()


def _safe_json_response(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_telegram_network_error(error: Exception) -> str:
    message = str(error)
    lower_message = message.lower()
    if "handshake" in lower_message and "timed out" in lower_message:
        return (
            "TLS handshake timed out when connecting to api.telegram.org. "
            "Check outbound network, DNS/firewall rules, or Telegram proxy availability."
        )
    return message


def _telegram_request_with_retry(
    method: str,
    url: str,
    *,
    timeout: httpx.Timeout,
    params: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
    attempts: int = 3,
) -> tuple[httpx.Response | None, str | None]:
    last_error: Exception | None = None

    for attempt in range(max(attempts, 1)):
        try:
            if method == "GET":
                return httpx.get(url, params=params, timeout=timeout), None
            if method == "POST":
                request_kwargs: dict[str, Any] = {"json": json_payload, "timeout": timeout}
                if params:
                    request_kwargs["params"] = params
                return httpx.post(url, **request_kwargs), None
            return None, f"Unsupported method: {method}"
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.4 * (attempt + 1))
                continue
            return None, _format_telegram_network_error(exc)
        except httpx.HTTPError as exc:
            return None, str(exc)

    if last_error is None:
        return None, "Unknown Telegram network error"
    return None, _format_telegram_network_error(last_error)


def _extract_telegram_chat_id(updates: list[dict[str, Any]]) -> int | str | None:
    for update in reversed(updates):
        for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
            chat = (update.get(key) or {}).get("chat")
            if isinstance(chat, dict) and chat.get("id") is not None:
                return chat["id"]
        chat = (update.get("my_chat_member") or {}).get("chat")
        if isinstance(chat, dict) and chat.get("id") is not None:
            return chat["id"]
    return None


def _detect_webhook_provider(target_url: str) -> str:
    parsed = urlparse(target_url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "feishu" in host or "larksuite" in host:
        return "feishu"
    if "telegram" in host and "sendmessage" in path:
        return "telegram"
    return "generic"


def _render_webhook_text(event: AutomationEvent, *, max_length: int) -> str:
    payload_text = json.dumps(event.payload, ensure_ascii=False, indent=2, sort_keys=True)
    lines = [
        "Aerisun automation event",
        f"Event: {event.event_type}",
        f"Target: {event.target_type}:{event.target_id}",
        f"Event ID: {event.event_id}",
        "",
        payload_text,
    ]
    text = "\n".join(lines)
    if len(text) <= max_length:
        return text
    return text[: max_length - 18].rstrip() + "\n... (truncated)"


def _sign_feishu_url(target_url: str, secret: str) -> str:
    if not secret:
        return target_url
    parsed = urlparse(target_url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    timestamp = str(int(datetime.now(UTC).timestamp()))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    query_items.update(
        {
            "timestamp": timestamp,
            "sign": base64.b64encode(digest).decode("utf-8"),
        }
    )
    return urlunparse(parsed._replace(query=urlencode(query_items)))


def _build_webhook_request(
    subscription,
    delivery: WebhookDelivery | AutomationEvent,
) -> tuple[str, dict[str, Any], dict[str, str]]:
    if isinstance(delivery, AutomationEvent):
        event = delivery
        target_url = str(subscription.target_url or "").strip()
        headers_data = dict(subscription.headers or {})
    else:
        event = AutomationEvent(**dict(delivery.payload or {}))
        target_url = str(delivery.target_url or "").strip()
        headers_data = dict(delivery.headers or {})

    provider = _detect_webhook_provider(target_url)
    headers = {str(key): str(value) for key, value in headers_data.items()}
    headers.setdefault("Content-Type", "application/json")

    if provider == "feishu":
        url = _sign_feishu_url(target_url, str(subscription.secret or "").strip())
        payload = {
            "msg_type": "text",
            "content": {"text": _render_webhook_text(event, max_length=28000)},
        }
        return url, payload, headers

    if provider == "telegram":
        parsed = urlparse(target_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        chat_id = str(query.get("chat_id") or "").strip()
        if not chat_id:
            raise ValidationError("Telegram webhook target_url must include chat_id")
        payload = {
            "chat_id": chat_id,
            "text": _render_webhook_text(event, max_length=3500),
        }
        parse_mode = str(query.get("parse_mode") or "").strip()
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return target_url, payload, headers

    if isinstance(delivery, AutomationEvent):
        return target_url, dict(event.payload or {}), headers

    return target_url, dict(delivery.payload or {}), headers
