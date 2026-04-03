"""Workflow draft management — create, continue, and finalize AI-planned workflow drafts."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from aerisun.domain.automation._helpers import (
    ensure_workflow_ai_model,
    normalize_string_list,
    now_utc,
    planning_model_config,
)
from aerisun.domain.automation.runtime import invoke_model_json
from aerisun.domain.automation.schemas import (
    AgentWorkflowCreate,
    AgentWorkflowDraftBoundaryRead,
    AgentWorkflowDraftChatWrite,
    AgentWorkflowDraftCompileReportRead,
    AgentWorkflowDraftCreateRead,
    AgentWorkflowDraftCreateWrite,
    AgentWorkflowDraftMessageRead,
    AgentWorkflowDraftOptionRead,
    AgentWorkflowDraftPreviewRead,
    AgentWorkflowDraftQuestionRead,
    AgentWorkflowDraftRead,
    AgentWorkflowUpdate,
)
from aerisun.domain.automation.settings import (
    clear_agent_workflow_draft_payload,
    create_agent_workflow,
    default_workflow_key_for_template,
    find_agent_workflow,
    get_agent_workflow_draft_payload,
    save_agent_workflow_draft_payload,
    update_agent_workflow,
    workflow_template_rule,
)
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

logger = logging.getLogger(__name__)

WORKFLOW_DRAFT_ID = "global"
WORKFLOW_DRAFT_MAX_MESSAGES = 20

AI_WORKFLOW_TEMPLATES = (
    "community_moderation",
    "comment_moderation",
    "guestbook_moderation",
    "content_publish_review",
)


def _preview_from_workflow(raw: Any) -> AgentWorkflowDraftPreviewRead | None:
    if raw is None:
        return None
    try:
        return AgentWorkflowDraftPreviewRead.model_validate(raw)
    except Exception:
        logger.warning("Failed to parse workflow draft preview payload", exc_info=True)
        return None


def _draft_from_payload(raw: dict[str, Any] | None) -> AgentWorkflowDraftRead | None:
    if not raw:
        return None
    try:
        return AgentWorkflowDraftRead.model_validate(raw)
    except Exception:
        logger.warning("Failed to parse agent workflow draft payload", exc_info=True)
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
    return messages[-16:]


def _draft_conversation_text(messages: list[AgentWorkflowDraftMessageRead]) -> str:
    return "\n".join(f"{item.role}: {item.content}" for item in messages)


def _normalize_draft_options(raw: Any) -> list[AgentWorkflowDraftOptionRead]:
    if not isinstance(raw, list):
        return []
    options: list[AgentWorkflowDraftOptionRead] = []
    for item in raw[:6]:
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
        questions.append(
            AgentWorkflowDraftQuestionRead(
                key=str(item.get("key") or f"q{index}").strip() or f"q{index}",
                prompt=prompt,
                options=options,
            )
        )
    return questions


def _normalize_draft_boundary(raw: Any) -> AgentWorkflowDraftBoundaryRead:
    if not isinstance(raw, dict):
        return AgentWorkflowDraftBoundaryRead()
    return AgentWorkflowDraftBoundaryRead(
        requires_platform_extension=bool(raw.get("requires_platform_extension")),
        summary=str(raw.get("summary") or "").strip(),
        missing_capabilities=normalize_string_list(raw.get("missing_capabilities")),
        recommended_actions=normalize_string_list(raw.get("recommended_actions")),
    )


def continue_agent_workflow_draft(
    session: Session,
    payload: AgentWorkflowDraftChatWrite,
    *,
    progress_callback: Callable[[str, dict[str, Any] | None], None] | None = None,
) -> AgentWorkflowDraftRead:
    def emit_progress(status: str, extra: dict[str, Any] | None = None) -> None:
        if progress_callback is not None:
            progress_callback(status, extra)

    emit_progress("loading_draft")
    draft = get_agent_workflow_draft(session)
    now = now_utc()
    messages = list(draft.messages if draft else [])
    messages.append(AgentWorkflowDraftMessageRead(role="user", content=payload.message.strip(), created_at=now))
    trimmed_messages = _trim_draft_messages(messages)
    model_config = ensure_workflow_ai_model(session)
    emit_progress("invoking_planner_model")
    parsed = invoke_model_json(
        planning_model_config(model_config, minimum_timeout_seconds=60),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Aerisun workflow planning assistant. "
                    "Return strict JSON only with keys assistant_message, summary, working_document, "
                    "ready_to_create, suggested_template, questions, current_question, options, boundary, stage, and semantic_workflow."
                ),
            },
            {
                "role": "user",
                "content": _draft_conversation_text(trimmed_messages),
            },
        ],
    )
    emit_progress("processing_model_output")

    assistant_message = str(parsed.get("assistant_message") or "我先整理一下需求。").strip()
    summary = str(parsed.get("summary") or (draft.summary if draft else "")).strip()
    working_document = str(parsed.get("working_document") or (draft.working_document if draft else "")).strip()
    suggested_template = (
        str(parsed.get("suggested_template") or (draft.suggested_template if draft else "") or "").strip() or None
    )
    boundary = _normalize_draft_boundary(parsed.get("boundary"))
    questions = _normalize_draft_questions(parsed.get("questions"))
    current_question = str(parsed.get("current_question") or "").strip()
    options = _normalize_draft_options(parsed.get("options"))
    if not questions and current_question and options:
        questions = [AgentWorkflowDraftQuestionRead(key="q1", prompt=current_question, options=options)]
    if questions:
        current_question = questions[0].prompt
        options = questions[0].options
    ready_to_create = bool(parsed.get("ready_to_create")) and not boundary.requires_platform_extension
    if ready_to_create and suggested_template not in AI_WORKFLOW_TEMPLATES:
        ready_to_create = False
    stage = str(parsed.get("stage") or "").strip() or (
        "blocked" if boundary.requires_platform_extension else "semantic_review" if ready_to_create else "planning"
    )
    semantic_preview = _preview_from_workflow(parsed.get("semantic_workflow")) or (
        draft.semantic_preview if draft else None
    )

    trimmed_messages.append(
        AgentWorkflowDraftMessageRead(role="assistant", content=assistant_message, created_at=now_utc())
    )

    next_draft = AgentWorkflowDraftRead(
        id=WORKFLOW_DRAFT_ID,
        status="ready" if ready_to_create else "active",
        stage=stage,
        summary=summary,
        ready_to_create=ready_to_create,
        suggested_template=suggested_template,
        boundary=boundary,
        questions=[] if ready_to_create else questions,
        current_question="" if ready_to_create else current_question,
        options=[] if ready_to_create else options,
        working_document=working_document,
        sketch_preview=payload.sketch_workflow or (draft.sketch_preview if draft else None),
        semantic_preview=semantic_preview,
        graph_candidate=draft.graph_candidate if draft else None,
        compile_report=draft.compile_report if draft else AgentWorkflowDraftCompileReportRead(),
        messages=_trim_draft_messages(trimmed_messages),
        created_at=draft.created_at if draft else now,
        updated_at=now_utc(),
    )
    emit_progress("saving_draft")
    return _persist_agent_workflow_draft(session, next_draft)


def create_agent_workflow_from_draft(
    session: Session,
    payload: AgentWorkflowDraftCreateWrite,
) -> AgentWorkflowDraftCreateRead:
    draft = get_agent_workflow_draft(session)
    if draft is None:
        raise ResourceNotFound("Workflow draft not found")
    if draft.boundary.requires_platform_extension:
        raise ValidationError(draft.boundary.summary or "Workflow draft exceeds current platform boundary")
    if not draft.ready_to_create and not payload.force:
        raise ValidationError("Workflow draft is not ready to create yet")

    model_config = ensure_workflow_ai_model(session)
    parsed = invoke_model_json(
        planning_model_config(model_config, minimum_timeout_seconds=90),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Aerisun workflow execution assistant. "
                    "Return strict JSON only with keys summary, analysis, template_key, used_capabilities, and workflow."
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

    template_key = str(parsed.get("template_key") or draft.suggested_template or "").strip()
    if template_key not in AI_WORKFLOW_TEMPLATES:
        template_key = "community_moderation"
    rule = workflow_template_rule(template_key)
    workflow_payload = dict(parsed.get("workflow") or {})
    default_key = default_workflow_key_for_template(template_key)
    workflow_key = (
        default_key
        if template_key == "community_moderation"
        else str(workflow_payload.get("key") or default_key).strip() or default_key
    )
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

    clear_agent_workflow_draft(session)
    return AgentWorkflowDraftCreateRead(
        ok=True,
        summary=str(parsed.get("summary") or "Workflow created successfully."),
        draft_cleared=True,
        workflow=workflow,
    )
